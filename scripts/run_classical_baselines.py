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

TRAINING-SIZE SWEEP
    --n-per-class takes several values and writes one file per size
    (<dataset>_matched_n<size>.jsonl). This is the learning-curve control and
    the fix for fraud's ceiling: at 250 per class fraud sits at PR-AUC 0.964
    with 0.036 of headroom, so no kernel difference has room to appear. The
    small-data regime is also the one quantum-kernel advantage claims are
    actually about.

Usage:
    PYTHONPATH=src python scripts/run_classical_baselines.py --dataset churn --track matched
    PYTHONPATH=src python scripts/run_classical_baselines.py --dataset fraud --track unconstrained
    PYTHONPATH=src python scripts/run_classical_baselines.py --dataset churn --track matched --shuffle-labels
    # quick smoke test:
    PYTHONPATH=src python scripts/run_classical_baselines.py --dataset synthetic --track matched --seeds 0 1 --qubits 2 4 --n-per-class 40
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

from qbench.data import SEEDS, balanced_subsample, load_dataset, make_split, shuffle_labels  # noqa: E402
from qbench.features import MAPPINGS, fit_mapping, scale_to_angles  # noqa: E402
from qbench.kernels.classical import build_classical_kernel  # noqa: E402
from qbench.metrics import ap_chance_for_record  # noqa: E402
from qbench.tuning import C_GRID, matched_grids, tune_and_evaluate, unconstrained_grids  # noqa: E402

KERNELS = ("linear", "rbf", "poly")


def gram_fn(name):
    return lambda p: build_classical_kernel(name, **p)


def run_matched_seed(X, y, seed, n_per_class, mappings, qubits, shuffle=False):
    Xs, ys = balanced_subsample(X, y, n_per_class=n_per_class, seed=seed)
    if shuffle:
        ys = shuffle_labels(ys, seed)
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
                rec.update(track="matched", mapping=mapping, n_qubits=nq,
                           n_per_class=int(n_per_class), shuffled=bool(shuffle))
                records.append(rec)
    return records


def run_unconstrained_seed(X, y, seed, max_per_class, shuffle=False):
    Xs, ys = balanced_subsample(X, y, n_per_class=max_per_class, seed=seed)
    if shuffle:
        ys = shuffle_labels(ys, seed)
    X_tr, X_te, y_tr, y_te = make_split(Xs, ys, seed=seed)
    grids = unconstrained_grids(X_tr.shape[1])
    records = []
    for k in KERNELS:
        rec = tune_and_evaluate(k, gram_fn(k), grids[k], X_tr, y_tr, X_te, y_te, seed=seed)
        rec.update(track="unconstrained", mapping="none", n_qubits=None,
                   n_features=int(X_tr.shape[1]), shuffled=bool(shuffle))
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


def negative_control_verdict(records):
    """Read the label-shuffled run against the correct null, not against the base rate.

    CORRECTED 23 Sep 2026. The first version of this function asserted that
    PR-AUC on shuffled labels has expectation equal to the test base rate. It
    does not. Average precision of a RANDOM ranking is upward-biased at finite
    sample size: 0.5154 at 150 balanced test points, 0.5516 at 30. Read against
    the base rate, the first control run appeared to show a 2.2-sigma leak in a
    pipeline that is clean. See qbench.metrics for the exact expectation and
    the derivation.

    ROC-AUC is exactly 0.5 under the null at any sample size, so it is the
    honest headline and is reported first.

    The standard error printed is OPTIMISTIC: records within a seed share a
    train/test split, so they are correlated and the effective sample size is
    nearer the number of seeds than the number of records. Treat it as a rough
    scale, not a p-value, and read the per-kernel maxima alongside it.
    """
    roc = np.array([r["test_roc_auc"] for r in records])
    ap_ = np.array([r["test_average_precision"] for r in records])
    chance = np.array([ap_chance_for_record(r) for r in records])
    base = np.array([r["test_base_rate"] for r in records])
    resid = ap_ - chance
    n_seeds = len({r["seed"] for r in records})

    def sigma(x, null):
        se = x.std(ddof=1) / np.sqrt(max(n_seeds, 1))
        return (x.mean() - null) / se if se else 0.0

    print("\nNEGATIVE CONTROL VERDICT (labels permuted)")
    print(f"  ROC-AUC                    : mean {roc.mean():.4f}  sd {roc.std(ddof=1):.4f}  "
          f"-> {sigma(roc, 0.5):+.2f} sigma from the exact null of 0.500")
    print(f"  AP vs CHANCE (not base)    : mean {resid.mean():+.4f}  sd {resid.std(ddof=1):.4f}  "
          f"-> {sigma(resid, 0.0):+.2f} sigma")
    print(f"     base rate {base.mean():.4f}, chance AP {chance.mean():.4f} "
          f"(the gap of {chance.mean() - base.mean():+.4f} is expected, not leakage)")
    print(f"     for reference, AP minus BASE would read {(ap_ - base).mean():+.4f}, "
          f"which is the wrong comparison")
    worst = max(records, key=lambda r: r["test_roc_auc"])
    print(f"  worst cell by ROC-AUC      : {worst['method']} {worst['mapping']} q={worst['n_qubits']} "
          f"seed={worst['seed']} -> {worst['test_roc_auc']:.4f}  "
          f"(max of {len(records)} draws; ~{0.5 + 3.2 * roc.std(ddof=1):.4f} expected by chance)")
    print(f"  ({len(records)} records, {n_seeds} seeds; sigma uses the seed count, not the record count)")
    print("  Clean means ROC-AUC within about 2 sigma of 0.500 and the AP residual within about")
    print("  2 sigma of zero, with no consistent sign. A real leak shows in BOTH at once.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, choices=["churn", "fraud", "synthetic"])
    ap.add_argument("--track", required=True, choices=["matched", "unconstrained"])
    ap.add_argument("--seeds", type=int, nargs="+", default=SEEDS)
    ap.add_argument("--mappings", nargs="+", default=list(MAPPINGS))
    ap.add_argument("--qubits", type=int, nargs="+", default=[4, 6, 8, 10, 12])
    ap.add_argument("--n-per-class", type=int, nargs="+", default=[50, 100, 250],
                    help="matched track: one run per training size. The sweep is the "
                         "learning-curve control AND the answer to fraud's ceiling effect: "
                         "at 250/class fraud sits at PR-AUC 0.964 with almost no headroom, "
                         "and the small-data regime is the one this literature argues about.")
    ap.add_argument("--max-per-class", type=int, default=1000, help="unconstrained track cap")
    ap.add_argument("--jobs", type=int, default=-1)
    ap.add_argument("--shuffle-labels", action="store_true",
                    help="NEGATIVE CONTROL: permute labels before splitting. Writes to "
                         "<dataset>_<track>_shuffled.jsonl and never overwrites a real run. "
                         "Expected PR-AUC is the base rate; anything above it is leakage.")
    ap.add_argument("--out-dir", default=str(ROOT / "results" / "runs" / "classical"))
    args = ap.parse_args()

    X, y, names = load_dataset(args.dataset)
    print(f"dataset={args.dataset} track={args.track} shape={X.shape} positives={int(y.sum())}")
    print(f"seeds={args.seeds}")
    if args.shuffle_labels:
        print("NEGATIVE CONTROL: labels permuted before splitting. These are not results.")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_shuffled" if args.shuffle_labels else ""
    commit = git_commit()

    # One output file per training size. Separate files, not one mixed file:
    # every downstream analysis pairs records within a cell, and a size column
    # silently mixed into that pairing would be a bug nobody would see.
    sizes = args.n_per_class if args.track == "matched" else [None]
    if args.track == "matched":
        print(f"n_per_class sweep={sizes}  mappings={args.mappings}  qubits={args.qubits}")
    else:
        print(f"max_per_class={args.max_per_class}  features={X.shape[1]}")

    written = []
    for size in sizes:
        t0 = time.perf_counter()
        if args.track == "matched":
            print(f"\n{'=' * 70}\nn_per_class={size}  ({2 * size} points, "
                  f"{int(2 * size * 0.7)} train / {2 * size - int(2 * size * 0.7)} test)\n{'=' * 70}")
            jobs = (delayed(run_matched_seed)(X, y, s, size, args.mappings, args.qubits,
                                              args.shuffle_labels) for s in args.seeds)
        else:
            jobs = (delayed(run_unconstrained_seed)(X, y, s, args.max_per_class, args.shuffle_labels)
                    for s in args.seeds)
        per_seed = Parallel(n_jobs=args.jobs)(jobs)
        records = [r for batch in per_seed for r in batch]
        elapsed = time.perf_counter() - t0

        meta = {"dataset": args.dataset, "git_commit": commit, "c_grid": list(C_GRID),
                "elapsed_seconds": elapsed, "shuffled": bool(args.shuffle_labels),
                "n_seeds": len(args.seeds)}
        tag = f"_n{size}" if size is not None else ""
        out = out_dir / f"{args.dataset}_{args.track}{tag}{suffix}.jsonl"
        with out.open("w") as f:
            for r in records:
                f.write(json.dumps({**meta, **r}) + "\n")

        summarise(records)
        if args.shuffle_labels:
            negative_control_verdict(records)
        print(f"\n{len(records)} records -> {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
        print(f"wall-clock {elapsed:.1f}s")
        written.append((out, len(records), elapsed))

    if len(written) > 1:
        total = sum(e for _, _, e in written)
        print(f"\n{'=' * 70}\nSWEEP COMPLETE: {len(written)} files, {total:.1f}s total")
        for out, n, e in written:
            print(f"  {out.name:<44} {n:>5} records  {e:>8.1f}s")


if __name__ == "__main__":
    main()
