#!/usr/bin/env python3
"""Week 3: tuned classical kernel SVM baselines, on two tracks.

MATCHED (primary)
    Exactly the data the quantum kernels will see: a class-balanced subsample
    of 2 x n_per_class points (default 250 per class, 500 total), mapped to
    n_qubits dimensions and scaled to rotation angles in [0, pi]. Only the
    kernel differs from the quantum track. Required for the geometric
    difference, which needs both Gram matrices over the same points.

UNCONSTRAINED (reference ceiling)
    All features, standardised, on a larger balanced sample (default up to
    1000 per class). Reported separately and never mixed into the paired
    tests. It answers: what does squeezing to a few qubits and a few hundred
    points cost against what a practitioner would actually deploy?

Every (dataset, seed, mapping, n_qubits, kernel) cell is tuned by nested CV
(qbench.tuning) and written as one JSON line to results/runs/classical/.

Usage:
    PYTHONPATH=src python scripts/run_classical_baselines.py --dataset churn --track matched
    PYTHONPATH=src python scripts/run_classical_baselines.py --dataset fraud --track unconstrained
    # quick smoke test:
    PYTHONPATH=src python scripts/run_classical_baselines.py --dataset synthetic --track matched --seeds 0 1 --qubits 2 4
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qbench.data import SEEDS, balanced_subsample, load_dataset, make_split  # noqa: E402
from qbench.features import MAPPINGS, fit_mapping, scale_to_angles  # noqa: E402
from qbench.kernels.classical import build_classical_kernel  # noqa: E402
from qbench.tuning import C_GRID, matched_grids, tune_and_evaluate, unconstrained_grids  # noqa: E402

KERNELS = ("linear", "rbf", "poly")


def gram_fn(name):
    return lambda p: build_classical_kernel(name, **p)


def run_matched_seed(X, y, seed, n_per_class, mappings, qubits):
    Xs, ys = balanced_subsample(X, y, n_per_class=n_per_class, seed=seed)
    X_tr, X_te, y_tr, y_te = make_split(Xs, ys, seed=seed)
    records = []
    for mapping in mappings:
        for nq in qubits:
            if mapping != "randproj" and nq > X_tr.shape[1]:
                continue
            Xm, transform = fit_mapping(X_tr, y_tr, nq, mapping, seed=seed)
            Xa_tr, to_angles = scale_to_angles(Xm)
            Xa_te = to_angles(transform(X_te))
            grids = matched_grids(Xa_tr.shape[1])
            for k in KERNELS:
                rec = tune_and_evaluate(k, gram_fn(k), grids[k], Xa_tr, y_tr, Xa_te, y_te, seed=seed)
                rec.update(track="matched", mapping=mapping, n_qubits=nq)
                records.append(rec)
    return records


def run_unconstrained_seed(X, y, seed, max_per_class):
    Xs, ys = balanced_subsample(X, y, n_per_class=max_per_class, seed=seed)
    X_tr, X_te, y_tr, y_te = make_split(Xs, ys, seed=seed)
    grids = unconstrained_grids(X_tr.shape[1])
    records = []
    for k in KERNELS:
        rec = tune_and_evaluate(k, gram_fn(k), grids[k], X_tr, y_tr, X_te, y_te, seed=seed)
        rec.update(track="unconstrained", mapping="none", n_qubits=None, n_features=int(X_tr.shape[1]))
        records.append(rec)
    return records


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return None


def summarise(records):
    groups = defaultdict(list)
    for r in records:
        groups[(r["mapping"], r["n_qubits"], r["method"])].append(r)
    print(f"\n{'mapping':<10}{'qubits':>7}{'kernel':>8}{'seeds':>7}{'test PR-AUC':>16}{'base':>8}{'edge-flagged':>14}")
    print("-" * 70)
    edge_total = 0
    for (mapping, nq, method), rows in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0, kv[0][2])):
        ap = np.array([r["test_average_precision"] for r in rows])
        base = np.mean([r["test_base_rate"] for r in rows])
        n_edge = sum(1 for r in rows if r["edge"])
        edge_total += n_edge
        q = "-" if nq is None else str(nq)
        print(f"{mapping:<10}{q:>7}{method:>8}{len(rows):>7}{ap.mean():>10.4f} ± {ap.std(ddof=1) if len(ap) > 1 else 0:.3f}"
              f"{base:>8.3f}{n_edge:>9}/{len(rows)}")
    n_bad_fits = sum(r["n_nonconverged"] for r in records)
    n_final_bad = sum(1 for r in records if not r["final_converged"])
    n_fallback = sum(1 for r in records if r.get("final_fallback_rank", 0) > 0)
    print(f"\nsolver: {n_bad_fits} inner-CV fits failed to converge (excluded, never scored); "
          f"{n_fallback} final fits fell back to the next-best setting; "
          f"{n_final_bad} final models failed to converge after fallback.")
    if n_final_bad:
        print("  WARNING: a non-converged final model's test score is not trustworthy.")
    print(f"\n{edge_total} of {len(records)} tuned models chose a hyperparameter on the edge of its grid.")
    if edge_total:
        counts = defaultdict(int)
        for r in records:
            for f in r["edge"]:
                counts[f.split("=")[0] + " " + f.split("(")[-1].rstrip(")")] += 1
        for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"  {v:4d} x {k}")
        print("  Edge choices mean the optimum may lie outside the grid. Widen it before")
        print("  calling that baseline tuned.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, choices=["churn", "fraud", "synthetic"])
    ap.add_argument("--track", required=True, choices=["matched", "unconstrained"])
    ap.add_argument("--seeds", type=int, nargs="+", default=SEEDS)
    ap.add_argument("--mappings", nargs="+", default=list(MAPPINGS))
    ap.add_argument("--qubits", type=int, nargs="+", default=[2, 3, 4, 6, 8])
    ap.add_argument("--n-per-class", type=int, default=250, help="matched track: quantum-sized subsample")
    ap.add_argument("--max-per-class", type=int, default=1000, help="unconstrained track cap")
    ap.add_argument("--jobs", type=int, default=-1)
    ap.add_argument("--out-dir", default=str(ROOT / "results" / "runs" / "classical"))
    args = ap.parse_args()

    X, y, names = load_dataset(args.dataset)
    print(f"dataset={args.dataset} track={args.track} shape={X.shape} positives={int(y.sum())}")
    print(f"seeds={args.seeds}")
    if args.track == "matched":
        print(f"n_per_class={args.n_per_class}  mappings={args.mappings}  qubits={args.qubits}")
    else:
        print(f"max_per_class={args.max_per_class}  features={X.shape[1]}")

    t0 = time.perf_counter()
    if args.track == "matched":
        jobs = (delayed(run_matched_seed)(X, y, s, args.n_per_class, args.mappings, args.qubits) for s in args.seeds)
    else:
        jobs = (delayed(run_unconstrained_seed)(X, y, s, args.max_per_class) for s in args.seeds)
    per_seed = Parallel(n_jobs=args.jobs)(jobs)
    records = [r for batch in per_seed for r in batch]
    elapsed = time.perf_counter() - t0

    meta = {"dataset": args.dataset, "git_commit": git_commit(), "c_grid": list(C_GRID), "elapsed_seconds": elapsed}
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{args.dataset}_{args.track}.jsonl"
    with out.open("w") as f:
        for r in records:
            f.write(json.dumps({**meta, **r}) + "\n")

    summarise(records)
    print(f"\n{len(records)} records -> {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    print(f"wall-clock {elapsed:.1f}s")


if __name__ == "__main__":
    main()
