#!/usr/bin/env python3
"""Week 4: the four frozen quantum kernels, on the matched track.

Runs exactly what docs/pre-registration.md section 3 freezes: angle and IQP
embeddings at one and two repetitions, on `lightning.qubit`, through the same
`tune_and_evaluate` the classical baselines went through. Identical folds,
identical solver, identical selection rule; only the Gram matrix differs. That
symmetry is what makes the week-9 paired tests valid.

RESUMABILITY IS THE POINT
-------------------------
This run is tens of hours across several nights. A crash at hour 20 must not
mean starting over, and a laptop that sleeps must not corrupt the output. So:

  * records are appended and flushed one cell at a time, never held in memory
    until the end;
  * on restart, completed (seed, mapping, qubits) cells are read back from the
    output file and skipped;
  * --dry-run prints the plan, the remaining work and the projected wall clock
    without computing anything.

The classical runner could afford to collect everything and write once because
it finished in half an hour. This one cannot.

ORDER OF WORK
-------------
Cells are ordered so the PRIMARY cells of the pre-registration run first
(churn PCA/12, fraud SelectKBest/8). If something is wrong with the quantum
path, it shows up in the first hour rather than the last.

THE CONTROL RUNS FIRST
----------------------
Section 7 of the pre-registration commits to a label-shuffled control on the
quantum path. Run it with --shuffle-labels BEFORE any real result is computed,
so there is no opportunity to read a real number before knowing the pipeline
is clean.

Usage:
    # 1. the control, on the primary cells only
    PYTHONPATH=src python scripts/run_quantum_kernels.py --dataset churn --shuffle-labels --primary-only
    # 2. the plan, before committing a night to it
    PYTHONPATH=src python scripts/run_quantum_kernels.py --dataset churn --dry-run
    # 3. the real sweep, resumable
    PYTHONPATH=src python scripts/run_quantum_kernels.py --dataset churn
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qbench.data import SEEDS, balanced_subsample, load_dataset, make_split, shuffle_labels  # noqa: E402
from qbench.features import MAPPINGS, fit_mapping, scale_to_angles  # noqa: E402
from qbench.kernels.pennylane_kernels import available_devices  # noqa: E402
from qbench.kernels.quantum import (  # noqa: E402
    FROZEN_SETTINGS,
    QuantumGramFactory,
    expected_entries,
    setting_label,
)
from qbench.tuning import C_GRID, tune_and_evaluate  # noqa: E402

# docs/pre-registration.md section 3: the cell where the classical baseline is
# strongest, named in advance so it cannot be chosen after the fact.
PRIMARY_CELL = {"churn": ("pca", 12), "fraud": ("selectk", 8)}

# docs/pre-registration.md section 3 registers this backend. The library's own
# default is `default.qubit`, which is 1.4 to 2.5x slower; inheriting it here
# would have produced a run on an unregistered backend, with the projected
# wall clock computed from lightning's measured rates below. Caught by a dry
# run on 24 Sep 2026 before any compute was spent.
REGISTERED_DEVICE = "lightning.qubit"

# Measured on the target machine, results/analysis/backend_benchmark*.json.
# These are LIGHTNING rates. If the device changes, this table is wrong.
MS_PER_ENTRY = {4: 0.401, 6: 0.440, 8: 0.477, 10: 0.550, 12: 0.650}


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return None


def cell_order(dataset, mappings, qubits):
    """Primary cell first, then everything else in a stable order."""
    cells = [(m, q) for m in mappings for q in qubits]
    primary = PRIMARY_CELL.get(dataset)
    if primary in cells:
        cells.remove(primary)
        cells.insert(0, primary)
    return cells


def repair_jsonl(path):
    """Drop a trailing partial line left by an interrupted write.

    Found by a test on 24 Sep 2026. Resuming in append mode leaves a truncated
    final line in the file for good. `completed_keys` below tolerates it, but
    every analysis script reads JSONL with a bare json.loads and would fail
    weeks later on a file that looks complete. Repairing at startup keeps the
    output valid JSONL so nothing downstream needs to know this happened.

    Truncates at the FIRST unreadable line rather than trying to salvage past
    it: the file is append-only, so corruption can only be at the end, and
    guessing otherwise risks keeping records written after a failure.
    """
    if not path.exists():
        return 0
    data = path.read_bytes()
    keep = 0
    for line in data.splitlines(keepends=True):
        if not line.endswith(b"\n"):
            break
        try:
            json.loads(line)
        except json.JSONDecodeError:
            break
        keep += len(line)
    if keep != len(data):
        with path.open("r+b") as f:
            f.truncate(keep)
        return len(data) - keep
    return 0


def completed_keys(path):
    """(seed, mapping, n_qubits, setting) already in the output file.

    Tolerates a truncated final line, which is what a laptop sleeping
    mid-write leaves behind.
    """
    if not path.exists():
        return set()
    done = set()
    with path.open() as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            done.add((r["seed"], r["mapping"], r["n_qubits"], r["setting"]))
    return done


def run_cell(X, y, seed, n_per_class, mapping, nq, shuffle, device, done, out, meta):
    """One (seed, mapping, qubits) cell: all four settings, appended as they finish."""
    Xs, ys = balanced_subsample(X, y, n_per_class=n_per_class, seed=seed)
    if shuffle:
        ys = shuffle_labels(ys, seed)
    X_tr, X_te, y_tr, y_te = make_split(Xs, ys, seed=seed)
    if mapping != "randproj" and nq > X_tr.shape[1]:
        return 0, 0
    Xm, transform = fit_mapping(X_tr, y_tr, nq, mapping, seed=seed)
    Xa_tr, to_angles = scale_to_angles(Xm)
    Xa_te = to_angles(transform(X_te))

    factory = QuantumGramFactory(nq, device=device)
    written, t0 = 0, time.perf_counter()
    for params in FROZEN_SETTINGS:
        label = setting_label(params)
        if (seed, mapping, nq, label) in done:
            continue
        rec = tune_and_evaluate(f"quantum-{label}", factory.gram_fn, [dict(params)],
                                Xa_tr, y_tr, Xa_te, y_te, seed=seed)
        rec.update(track="matched", mapping=mapping, n_qubits=nq, setting=label,
                   embedding=params["embedding"], reps=params["reps"],
                   n_per_class=int(n_per_class), shuffled=bool(shuffle),
                   device=device, circuit_evaluations=factory.evaluations(),
                   cache_hits=factory.cache_hits())
        with out.open("a") as f:
            f.write(json.dumps({**meta, **rec}) + "\n")
            f.flush()
        written += 1
    factory.clear()
    return written, time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, choices=["churn", "fraud", "synthetic"])
    ap.add_argument("--seeds", type=int, nargs="+", default=SEEDS)
    ap.add_argument("--mappings", nargs="+", default=list(MAPPINGS))
    ap.add_argument("--qubits", type=int, nargs="+", default=[4, 6, 8, 10, 12])
    ap.add_argument("--n-per-class", type=int, default=250)
    ap.add_argument("--device", default=REGISTERED_DEVICE,
                    help="pre-registered backend; changing it is a logged deviation")
    ap.add_argument("--shuffle-labels", action="store_true",
                    help="NEGATIVE CONTROL. Run this BEFORE any real result, per "
                         "pre-registration section 7.")
    ap.add_argument("--primary-only", action="store_true",
                    help="only the pre-registered primary cell for this dataset")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan and the projected wall clock; compute nothing")
    ap.add_argument("--out-dir", default=str(ROOT / "results" / "runs" / "quantum"))
    args = ap.parse_args()

    usable = available_devices()
    if args.device not in usable:
        raise SystemExit(
            f"device {args.device!r} is not usable here (available: {usable}).\n"
            f"docs/pre-registration.md section 3 registers {REGISTERED_DEVICE!r}, and the cost\n"
            f"model in this script is measured on it. Install pennylane-lightning rather than\n"
            f"falling back: a run on a different backend is a deviation and must be recorded\n"
            f"in docs/deviations.md before it happens.")
    if args.device != REGISTERED_DEVICE:
        print(f"WARNING: running on {args.device!r}, not the registered {REGISTERED_DEVICE!r}. "
              f"The projected wall clock below is measured on the registered backend and does "
              f"not apply. Record this in docs/deviations.md.")

    X, y, _ = load_dataset(args.dataset)
    if args.primary_only:
        m, q = PRIMARY_CELL[args.dataset]
        args.mappings, args.qubits = [m], [q]
    cells = cell_order(args.dataset, args.mappings, args.qubits)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_shuffled" if args.shuffle_labels else ""
    out = out_dir / f"{args.dataset}_matched_n{args.n_per_class}{suffix}.jsonl"
    dropped = repair_jsonl(out)
    if dropped:
        print(f"repaired {out.name}: dropped {dropped} bytes of a partial trailing "
              f"record left by an interrupted run")
    done = completed_keys(out)

    n_train = int(2 * args.n_per_class * 0.7)
    n_test = 2 * args.n_per_class - n_train
    todo = [(s, m, q, setting_label(p)) for s in args.seeds for (m, q) in cells
            for p in FROZEN_SETTINGS
            if (s, m, q, setting_label(p)) not in done
            and (m == "randproj" or q <= X.shape[1])]

    print(f"dataset={args.dataset}  device={args.device}  n_per_class={args.n_per_class} "
          f"({n_train} train / {n_test} test)")
    print(f"settings={[setting_label(p) for p in FROZEN_SETTINGS]}  (all four run; g does not screen)")
    print(f"cells={len(cells)}  seeds={len(args.seeds)}  first cell={cells[0]}"
          f"{'  <- pre-registered primary' if cells[0] == PRIMARY_CELL.get(args.dataset) else ''}")
    if args.shuffle_labels:
        print("NEGATIVE CONTROL: labels permuted. These are not results.")
    print(f"already complete: {len(done)} records  |  remaining: {len(todo)} records")

    secs = 0.0
    for _, _, q, _ in todo:
        secs += expected_entries(n_train, n_test) * MS_PER_ENTRY.get(q, 0.65) / 1000
    print(f"projected wall clock from the measured cost model: {secs / 3600:.1f} h")
    print(f"-> {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")

    if args.dry_run:
        print("\ndry run: nothing computed.")
        return
    if not todo:
        print("\nnothing to do.")
        return

    meta = {"dataset": args.dataset, "git_commit": git_commit(), "c_grid": list(C_GRID),
            "n_seeds": len(args.seeds), "device": args.device,
            "shuffled": bool(args.shuffle_labels)}

    t0, total = time.perf_counter(), 0
    for i, (mapping, nq) in enumerate(cells, 1):
        for seed in args.seeds:
            written, elapsed = run_cell(X, y, seed, args.n_per_class, mapping, nq,
                                        args.shuffle_labels, args.device, done, out, meta)
            total += written
            if written:
                rate = (time.perf_counter() - t0) / total
                left = len(todo) - total
                print(f"  [{i}/{len(cells)}] {mapping}/{nq} seed={seed}  "
                      f"+{written} records in {elapsed:.0f}s  |  "
                      f"{total}/{len(todo)} done, ~{left * rate / 3600:.1f} h left", flush=True)

    print(f"\n{total} new records in {(time.perf_counter() - t0) / 3600:.2f} h")
    print("Re-running this command resumes; completed cells are skipped.")


if __name__ == "__main__":
    main()
