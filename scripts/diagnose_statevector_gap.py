#!/usr/bin/env python3
"""Why do two mathematically identical kernels give different decision scores?

On 25 Sep 2026 the statevector formulation of the quantum kernel reproduced
the pairwise fidelity protocol to 1e-15 in unit tests, and then produced
decision scores differing by up to 0.605 on the real control runs, with
average precision and ROC-AUC differing by under 0.001.

Three candidate causes, and they demand different responses:

  A. The Gram matrices genuinely differ on real data by more than the tests
     saw. Then the optimisation is wrong and is discarded.
  B. The pipeline is not deterministic: the same code, run twice, disagrees.
     Then the problem predates this change and every reproducibility claim in
     the project needs revisiting. This is the serious one.
  C. The SVM solver amplifies a 1e-15 kernel perturbation into a large shift
     in the decision function while leaving the ranking, and therefore both
     registered endpoints, essentially untouched. Then the optimisation is
     sound but the pipeline's sensitivity has to be characterised and stated,
     because it bounds what any paired test on PREDICTIONS (McNemar) can claim.

This measures all three on the real primary cell rather than arguing about
which is likelier.

Usage:
    PYTHONPATH=src python scripts/diagnose_statevector_gap.py --dataset churn
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from sklearn.svm import SVC

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qbench.data import balanced_subsample, load_dataset, make_split, shuffle_labels  # noqa: E402
from qbench.features import fit_mapping, scale_to_angles  # noqa: E402
from qbench.kernels.pennylane_kernels import build_pennylane_kernel  # noqa: E402
from qbench.kernels.quantum import FROZEN_SETTINGS, QuantumGramFactory, setting_label  # noqa: E402
from qbench.tuning import MAX_ITER  # noqa: E402

PRIMARY = {"churn": ("pca", 12), "fraud": ("selectk", 8)}


def prepare(dataset, seed, n_per_class, shuffle):
    X, y, _ = load_dataset(dataset)
    Xs, ys = balanced_subsample(X, y, n_per_class=n_per_class, seed=seed)
    if shuffle:
        ys = shuffle_labels(ys, seed)
    X_tr, X_te, y_tr, y_te = make_split(Xs, ys, seed=seed)
    mapping, nq = PRIMARY[dataset]
    Xm, transform = fit_mapping(X_tr, y_tr, nq, mapping, seed=seed)
    Xa_tr, to_angles = scale_to_angles(Xm)
    return Xa_tr, to_angles(transform(X_te)), y_tr, y_te, nq


def fit_scores(K_tr, y_tr, K_te, C):
    m = SVC(kernel="precomputed", C=C, class_weight="balanced", max_iter=MAX_ITER).fit(K_tr, y_tr)
    return m.decision_function(K_te), m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="churn", choices=["churn", "fraud"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-per-class", type=int, default=250)
    ap.add_argument("--shuffle-labels", action="store_true", default=True)
    ap.add_argument("--c-values", type=float, nargs="+", default=[1e-2, 1.0, 1e2, 1e4])
    args = ap.parse_args()

    Xa_tr, Xa_te, y_tr, y_te, nq = prepare(args.dataset, args.seed, args.n_per_class,
                                           args.shuffle_labels)
    print(f"{args.dataset} primary cell {PRIMARY[args.dataset]}  seed={args.seed}  "
          f"{len(y_tr)} train / {len(y_te)} test  shuffled={args.shuffle_labels}\n")

    for params in FROZEN_SETTINGS:
        label = setting_label(params)
        pw = build_pennylane_kernel(nq, embedding=params["embedding"],
                                    reps=params["reps"], device="lightning.qubit")
        sv = QuantumGramFactory(nq, device="lightning.qubit").gram_fn(dict(params))
        sv2 = QuantumGramFactory(nq, device="lightning.qubit").gram_fn(dict(params))

        Kp_tr = np.asarray(pw.evaluate(Xa_tr), dtype=float)
        Kp_te = np.asarray(pw.evaluate(Xa_te, Xa_tr), dtype=float)
        Ks_tr, Ks_te = sv(Xa_tr), sv(Xa_te, Xa_tr)
        Kr_tr, Kr_te = sv2(Xa_tr), sv2(Xa_te, Xa_tr)

        print(f"--- {label} ---")
        print(f"  A. Gram difference (pairwise vs statevector): train "
              f"{np.abs(Kp_tr - Ks_tr).max():.2e}   test {np.abs(Kp_te - Ks_te).max():.2e}")
        print(f"  B. statevector vs ITSELF, fresh factory     : train "
              f"{np.abs(Kr_tr - Ks_tr).max():.2e}   test {np.abs(Kr_te - Ks_te).max():.2e}")
        cond = np.linalg.cond(Kp_tr)
        print(f"     cond(K_train) = {cond:.3e}   eigenvalue range "
              f"[{np.linalg.eigvalsh(Kp_tr).min():.2e}, {np.linalg.eigvalsh(Kp_tr).max():.2e}]")

        for C in args.c_values:
            sp, mp = fit_scores(Kp_tr, y_tr, Kp_te, C)
            ss, ms = fit_scores(Ks_tr, y_tr, Ks_te, C)
            sr, _ = fit_scores(Kr_tr, y_tr, Kr_te, C)
            d = np.abs(sp - ss)
            shift = np.median(sp - ss)
            print(f"  C. C={C:<7g} |score diff| max {d.max():.3e} median {np.median(d):.3e}"
                  f" | after removing a constant shift {np.abs(sp - ss - shift).max():.3e}"
                  f" | rank corr {np.corrcoef(sp.argsort().argsort(), ss.argsort().argsort())[0,1]:.6f}"
                  f" | self-repeat {np.abs(ss - sr).max():.1e}"
                  f" | nSV {mp.n_support_.sum()} vs {ms.n_support_.sum()}")
        print()


if __name__ == "__main__":
    main()
