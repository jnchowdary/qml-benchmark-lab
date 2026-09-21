#!/usr/bin/env python3
"""Does predictive signal survive the squeeze down to n_qubits dimensions?

Why this exists
---------------
The quantum track can only afford 4 to 8 qubits, i.e. 4 to 8 features. The
churn dataset arrives as 30 columns, 26 of which are one-hot binaries. If the
mapping down to 4 dimensions destroys the signal, then every kernel comparison
at 4 qubits measures noise, a null result would be an artefact of the
representation rather than a finding about quantum kernels, and nothing in the
test suite would catch it.

This script measures that directly: it fits a plain classical SVM on each
candidate representation and reports PR-AUC against two reference points.

Reference points that make the numbers readable:
  baseline   = the positive class rate. A useless model scores this on PR-AUC.
  full       = classical SVM on ALL features, no reduction. The ceiling.
Anything close to `baseline` means the representation is dead.

Run:
    PYTHONPATH=src python scripts/diagnose_representation.py --dataset churn
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score
from sklearn.svm import SVC

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qbench.data import balanced_subsample, load_dataset, make_split  # noqa: E402
from qbench.features import fit_mapping, scale_to_angles  # noqa: E402

CONTINUOUS_HINTS = ("tenure", "MonthlyCharges", "TotalCharges", "Amount")


def describe_features(X, names):
    n_binary = sum(1 for j in range(X.shape[1]) if len(np.unique(X[:, j])) <= 2)
    print(f"  {X.shape[1]} features: {n_binary} binary, {X.shape[1] - n_binary} multi-valued")
    cont = [n for n in names if any(h in n for h in CONTINUOUS_HINTS)]
    print(f"  continuous-looking: {cont}")
    return cont


def fit_score(X_tr, y_tr, X_te, y_te, C=1.0):
    model = SVC(kernel="rbf", C=C, class_weight="balanced").fit(X_tr, y_tr)
    return float(average_precision_score(y_te, model.decision_function(X_te)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="churn")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--qubits", type=int, nargs="+", default=[2, 3, 4, 6, 8])
    ap.add_argument("--max-rows", type=int, default=4000,
                    help="Class-balanced cap on rows. SVC is ~O(n^2) in training rows, "
                         "so the full 284,807-row fraud set would run for hours.")
    ap.add_argument("--drop", nargs="*", default=[],
                    help="Column names to drop before anything else, e.g. --drop Time")
    args = ap.parse_args()

    X, y, names = load_dataset(args.dataset)
    print(f"\ndataset: {args.dataset}  shape={X.shape}  positives={int(y.sum())} ({y.mean():.6f})")

    if args.drop:
        keep = [i for i, n in enumerate(names) if n not in args.drop]
        dropped = [n for n in names if n in args.drop]
        missing = [c for c in args.drop if c not in names]
        if missing:
            raise SystemExit(f"--drop named columns not in this dataset: {missing}")
        X, names = X[:, keep], [names[i] for i in keep]
        print(f"  dropped {dropped} -> {X.shape[1]} features")

    if args.max_rows and len(X) > args.max_rows:
        X, y = balanced_subsample(X, y, n_per_class=args.max_rows // 2, seed=args.seed)
        print(f"  capped to {X.shape[0]} rows, class-balanced "
              f"(SVC is ~O(n^2); the full set would take hours)")
        print(f"  NOTE: the base rate is now {y.mean():.4f}, not the original. Every number"
              f" below is relative to THIS sample, not the population.")
    continuous = describe_features(X, names)

    X_tr, X_te, y_tr, y_te = make_split(X, y, seed=args.seed)

    baseline = float(y_te.mean())
    full = fit_score(X_tr, y_tr, X_te, y_te)
    print(f"\nreference points (PR-AUC)")
    print(f"  baseline (positive rate, a useless model) : {baseline:.4f}")
    print(f"  full feature set, no reduction            : {full:.4f}")
    print(f"  headroom the reduction must preserve      : {full - baseline:.4f}")

    cont_idx = [i for i, n in enumerate(names) if any(h in n for h in CONTINUOUS_HINTS)]

    print(f"\n{'mapping':<22}{'qubits':>7}{'PR-AUC':>10}{'vs baseline':>13}{'% of full':>11}")
    print("-" * 63)

    rows = []
    for strategy in ("pca", "selectk", "randproj"):
        for nq in args.qubits:
            try:
                Xm_tr, transform = fit_mapping(X_tr, y_tr, nq, strategy, seed=args.seed)
                Xa_tr, to_angles = scale_to_angles(Xm_tr)
                Xa_te = to_angles(transform(X_te))
                ap_score = fit_score(Xa_tr, y_tr, Xa_te, y_te)
            except Exception as e:  # noqa: BLE001
                print(f"{strategy:<22}{nq:>7}   FAILED: {type(e).__name__}: {e}")
                continue
            gain = ap_score - baseline
            pct = 100 * gain / (full - baseline) if full > baseline else float("nan")
            print(f"{strategy:<22}{nq:>7}{ap_score:>10.4f}{gain:>+13.4f}{pct:>10.1f}%")
            rows.append((strategy, nq, ap_score))

    # The control: do the 26 one-hot columns carry anything the 3 continuous
    # features do not already have? Runs regardless of the requested qubit counts,
    # because there are only len(cont_idx) continuous features available.
    def report(label, nq, ap_score):
        gain = ap_score - baseline
        pct = 100 * gain / (full - baseline) if full > baseline else float("nan")
        print(f"{label:<22}{nq:>7}{ap_score:>10.4f}{gain:>+13.4f}{pct:>10.1f}%")

    # Only meaningful where one-hot columns exist to be questioned (churn). On a
    # dataset with no binary columns (fraud) the 'continuous only' control
    # collapses to whatever the hint list happens to match, which means nothing.
    n_binary = sum(1 for j in range(X_tr.shape[1]) if len(np.unique(X_tr[:, j])) <= 2)
    if cont_idx and n_binary > 0 and len(cont_idx) >= 2:
        print()
        Xc_tr, Xc_te = X_tr[:, cont_idx], X_te[:, cont_idx]
        Xa_tr, to_angles = scale_to_angles(Xc_tr)
        report("continuous raw", len(cont_idx), fit_score(Xa_tr, y_tr, to_angles(Xc_te), y_te))
        for nq in sorted({q for q in args.qubits if q < len(cont_idx)}):
            Xm_tr, transform = fit_mapping(Xc_tr, y_tr, nq, "pca", seed=args.seed)
            Xa_tr, to_angles = scale_to_angles(Xm_tr)
            report("continuous pca", nq, fit_score(Xa_tr, y_tr, to_angles(transform(Xc_te)), y_te))

    print("\nHow to read this:")
    print("  '% of full' near 0   -> the representation is dead; a null quantum result")
    print("                          at that qubit count would mean nothing.")
    print("  '% of full' above ~60 -> the representation carries real signal and the")
    print("                          kernel comparison is measuring something.")
    print("  If a 'continuous' control row appears and matches the full-feature PCA,")
    print("  the one-hot columns are contributing noise and should be dropped.\n")


if __name__ == "__main__":
    main()
