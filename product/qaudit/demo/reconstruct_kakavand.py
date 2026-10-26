#!/usr/bin/env python3
"""Reconstruct audit records from a deposit that never emitted them.

ONE WORKFLOW, DEMONSTRATED ON ONE DEPOSIT
-----------------------------------------
    retained artefacts  ->  reconstructed evidence  ->  audit report

The subject is the hardware phase of Kakavand, Strohmeyer & Schlotter (2026),
arXiv:2604.18837, Zenodo 10.5281/zenodo.19197916, CC BY 4.0. Their endpoint is
balanced accuracy. The audit schema wants average precision and ROC-AUC, which
they never computed, so `scripts/foreign/kakavand_adapter.py` left those fields
absent and the audit reported what it could not answer. That was correct and it
was not the end of the matter.

They deposited the 60x60 hardware Gram matrices AND the labels, and their
scoring protocol is in `scripts/audit_hw_results.py` in the same deposit. So the
missing metrics are not absent: they are RECOMPUTABLE, by re-running their own
cross-validation against their own kernel. No QPU, no re-run of their pipeline,
nothing asked of them.

This is a distinct capability from parsing. Parsing recovers a value somebody
stored. This recomputes a value nobody stored, from artefacts somebody kept. The
two have different costs and different prerequisites, and the prerequisite here
is that a kernel matrix was published, which a vendor will not do.

WHAT THIS SCRIPT CLAIMS, AND WHAT IT DOES NOT
---------------------------------------------
It claims: re-running their documented protocol reproduces their six reported
balanced accuracies, and average precision and ROC-AUC follow from the same
fits.

It does NOT claim the reconstruction is their code. Reproducing six aggregate
figures is strong evidence that the protocol, the fold assignment and the
selection rule match. It is not proof that every implementation detail matches,
and it cannot be: their `phase3_hardware_runner.py`, which wrote `result.json`,
is NOT in the deposit. `audit_hw_results.py` is, and is what this follows.
Remaining assumptions are listed in ASSUMPTIONS below and printed on every run.

Every emitted record is marked `derived: true` and carries what it was derived
from, by which script, from which file, at which checksum, and which outer fold
it is. None of it is presented as deposited, and no two records from the same
experiment are independent experiments: they are five folds of one subsample.

Usage:
    KAKAVAND_DEPOSIT=... python reconstruct_kakavand.py --out derived.jsonl
    qaudit derived.jsonl --cell-fields dataset feature_map k_features n_qubits reducer
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from math import comb
from pathlib import Path

import numpy as np
import sklearn
from sklearn.metrics import (average_precision_score, balanced_accuracy_score,
                             roc_auc_score)
from sklearn.model_selection import StratifiedKFold
from sklearn.svm import SVC

# ---- their protocol, transcribed from scripts/audit_hw_results.py of the deposit
SEED = 42
C_GRID = [0.01, 0.1, 1.0, 10.0, 100.0]
N_SPLITS = 5

ASSUMPTIONS = [
    "The protocol is transcribed from scripts/audit_hw_results.py in the deposit: "
    "nested StratifiedKFold(5, shuffle=True, random_state=42), inner selection over "
    "C in [0.01, 0.1, 1, 10, 100] on mean balanced accuracy, then an outer fit at the "
    "selected C. phase3_hardware_runner.py, which wrote result.json, is NOT in the "
    "deposit, so this follows the audit script rather than the producing script.",

    "Fold assignment depends on scikit-learn's StratifiedKFold implementation. A "
    "future scikit-learn that changes shuffling would change the folds and so the "
    "per-fold figures. The version used is recorded in this run's provenance block.",

    "`seed` in each emitted record is the OUTER FOLD INDEX, 0 to 4, not the "
    "experiment's seed. The audit schema defines records sharing a seed as sharing a "
    "train/test partition, and under this design the fold is the partition. The real "
    "experimental seed, 42, is in the derivation block as `source_seed`.",

    "Reproducing six aggregate balanced accuracies is strong evidence that protocol, "
    "fold assignment and selection rule match. It does not establish that every "
    "implementation detail matches.",

    "Only the HARDWARE arm is reconstructable here. Their ideal and noisy arms need "
    "cached simulator kernels that the deposit does not contain, so no classical or "
    "simulator comparator is emitted and the cross-arm check has nothing to pair.",

    "`quantum_seconds` is NOT emitted. The deposit's hardware_metadata carries the "
    "field reading 0.0 on all six runs and the code that wrote it is absent, so its "
    "meaning is unresolved. Emitting 0.0 would assert a metered figure that nobody "
    "has confirmed. The audit's cost check therefore reports the limitation, which "
    "is the correct outcome.",
]


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def chance_ap(n, p):
    """Exact expected AP of a uniformly random ranking at this (n, p).

    At n=12 this is far above the base rate, which is the whole reason the audit
    has a chance-correction check. Reported per fold so a reader can see how
    little headroom a twelve-point average precision has.
    """
    if p <= 0 or p >= n:
        return float("nan")
    r = np.arange(1, n + 1, dtype=float)
    tot = 0.0
    for k in range(1, p + 1):
        pmf = np.array([comb(int(ri) - 1, k - 1) * comb(n - int(ri), p - k) / comb(n, p)
                        for ri in r])
        tot += k * float(np.sum(pmf / r))
    return tot / p


def fingerprint(y):
    """Hash of the labels IN ORDER, which is what makes a paired test checkable."""
    return hashlib.sha256(",".join(str(int(v)) for v in y).encode()).hexdigest()[:16]


def reconstruct(exp_dir):
    """One experiment -> (per-fold records, pooled summary, agreement check)."""
    z = np.load(exp_dir / "K_hardware.npz")
    K, y = z["K"], z["y"]
    meta = json.loads((exp_dir / "result.json").read_text(encoding="utf-8"))
    reported = meta["svm_results"]["hw"]["balanced_accuracy"]
    hw = meta["hardware_metadata"]

    cell = {"dataset": meta["dataset"], "feature_map": meta["feature_map"],
            "k_features": meta["k_features"], "n_qubits": hw["n_qubits"],
            "reducer": meta["reducer"]}

    outer = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    recs, fold_ba, fold_ap, fold_roc, pooled_s, pooled_y = [], [], [], [], [], []

    for fold, (tr, te) in enumerate(outer.split(K, y)):
        Ktr, Kte = K[np.ix_(tr, tr)], K[np.ix_(te, tr)]
        ytr, yte = y[tr], y[te]

        inner = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
        best_c, best_inner = C_GRID[0], -1.0
        for c in C_GRID:
            sc = []
            for i_tr, i_va in inner.split(Ktr, ytr):
                m = SVC(kernel="precomputed", C=c).fit(Ktr[np.ix_(i_tr, i_tr)], ytr[i_tr])
                sc.append(balanced_accuracy_score(ytr[i_va], m.predict(Ktr[np.ix_(i_va, i_tr)])))
            if float(np.mean(sc)) > best_inner:
                best_inner, best_c = float(np.mean(sc)), c

        m = SVC(kernel="precomputed", C=best_c).fit(Ktr, ytr)
        s = m.decision_function(Kte)
        pred = m.predict(Kte)
        ba = balanced_accuracy_score(yte, pred)
        ap = average_precision_score(yte, s)
        roc = roc_auc_score(yte, s)
        fold_ba.append(ba); fold_ap.append(ap); fold_roc.append(roc)
        pooled_s += [float(v) for v in s]; pooled_y += [int(v) for v in yte]

        n_pos, n_neg = int(yte.sum()), int(len(yte) - yte.sum())
        recs.append({
            # --- audit schema
            "method": "quantum-hardware",
            "provenance": "borrowed-hardware",
            "seed": fold,                       # the fold IS the partition; see ASSUMPTIONS
            "n_train": int(len(tr)),
            "n_test": int(len(te)),
            "test_base_rate": n_pos / len(te),
            "test_average_precision": float(ap),
            "test_roc_auc": float(roc),
            "test_label_fingerprint": fingerprint(yte),
            "shuffled": False,
            "final_converged": bool(m.fit_status_ == 0),
            "inner_score": best_inner,
            "params": {"C": best_c},
            "shots": int(hw["shots"]),
            "backend": hw["backend_name"],
            # quantum_seconds deliberately absent; see ASSUMPTIONS
            **cell,
            # --- derivation, so no reader mistakes this for a deposited record
            "derived": True,
            "derivation": {
                "by": "product/qaudit/demo/reconstruct_kakavand.py",
                "source_experiment": meta["experiment_id"],
                "source_seed": SEED,
                "outer_fold": fold,
                "of_folds": N_SPLITS,
                "sibling_folds_share_one_subsample": True,
                "endpoint_in_deposit": "balanced_accuracy",
                "endpoints_recomputed_here": ["average_precision", "roc_auc"],
                "recomputed_balanced_accuracy": float(ba),
                "fold_class_counts": {"positives": n_pos, "negatives": n_neg},
                "fold_chance_average_precision": chance_ap(len(te), n_pos),
                "dataset_level_base_rate": float(y.mean()),
                "dataset_level_class_counts": {"positives": int(y.sum()),
                                               "negatives": int(len(y) - y.sum())},
            },
        })

    mean_ba = float(np.mean(fold_ba))
    pooled = {
        "experiment": meta["experiment_id"],
        "reported_balanced_accuracy": reported,
        "recomputed_balanced_accuracy": mean_ba,
        "absolute_difference": abs(mean_ba - reported),
        "agrees": abs(mean_ba - reported) < 1e-12,
        # Pooled and per-fold are DIFFERENT QUANTITIES and both are reported.
        "per_fold_mean_average_precision": float(np.mean(fold_ap)),
        "per_fold_mean_roc_auc": float(np.mean(fold_roc)),
        "pooled_average_precision": float(average_precision_score(pooled_y, pooled_s)),
        "pooled_roc_auc": float(roc_auc_score(pooled_y, pooled_s)),
        "pooled_caveat":
            "Pooling concatenates decision_function values from five different SVMs, "
            "each with its own scale and intercept, so a pooled ranking mixes "
            "incomparable scores. Per-fold figures are each computed within one "
            "model and then averaged, which is the cleaner quantity, and each rests "
            "on twelve test points. Neither is preferred here: they are reported "
            "side by side because they answer different questions and this deposit "
            "does not support choosing between them.",
        "per_fold_average_precision": [float(v) for v in fold_ap],
        "per_fold_roc_auc": [float(v) for v in fold_roc],
        "per_fold_balanced_accuracy": [float(v) for v in fold_ba],
        "dataset_level_class_counts": {"positives": int(y.sum()),
                                       "negatives": int(len(y) - y.sum())},
        "dataset_level_base_rate": float(y.mean()),
        "source_sha256": {"K_hardware.npz": sha256(exp_dir / "K_hardware.npz"),
                          "result.json": sha256(exp_dir / "result.json")},
    }
    return recs, pooled


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deposit", default=os.environ.get("KAKAVAND_DEPOSIT"))
    ap.add_argument("--out", default="derived_kakavand_hw.jsonl")
    ap.add_argument("--summary", default="derived_kakavand_hw_provenance.json")
    a = ap.parse_args()
    if not a.deposit:
        raise SystemExit("\n  set KAKAVAND_DEPOSIT or pass --deposit.\n")

    root = Path(a.deposit) / "results" / "phase3_hardware"
    dirs = sorted(d for d in root.glob("HW-0*") if (d / "K_hardware.npz").exists())
    if not dirs:
        raise SystemExit(f"\n  no HW-* experiments under {root}\n")

    all_recs, summaries = [], []
    for d in dirs:
        recs, pooled = reconstruct(d)
        all_recs += recs
        summaries.append(pooled)

    Path(a.out).write_text("\n".join(json.dumps(r) for r in all_recs) + "\n",
                           encoding="utf-8")
    Path(a.summary).write_text(json.dumps({
        "what_this_is":
            "Records in this bundle are DERIVED, not deposited. The deposit reports "
            "balanced accuracy only. Average precision and ROC-AUC here were "
            "recomputed from the deposited Gram matrices and labels by re-running the "
            "deposit's own documented cross-validation. Five records per experiment "
            "are five folds of ONE subsample and are not independent experiments.",
        "source": {
            "citation": "Kakavand, Strohmeyer & Schlotter (2026), arXiv:2604.18837",
            "deposit": "Zenodo 10.5281/zenodo.19197916, CC BY 4.0",
            "path": str(Path(a.deposit).resolve()),
            "experiments": [d.name for d in dirs],
        },
        "protocol": {
            "transcribed_from": "scripts/audit_hw_results.py in the deposit",
            "outer": f"StratifiedKFold(n_splits={N_SPLITS}, shuffle=True, random_state={SEED})",
            "inner": f"StratifiedKFold(n_splits={N_SPLITS}, shuffle=True, random_state={SEED})",
            "c_grid": C_GRID,
            "inner_selection_metric": "balanced_accuracy",
            "estimator": "sklearn.svm.SVC(kernel='precomputed')",
        },
        "dependencies": {
            "python": sys.version.split()[0],
            "platform": f"{platform.system()} {platform.machine()}",
            "numpy": np.__version__,
            "scikit-learn": sklearn.__version__,
        },
        "assumptions": ASSUMPTIONS,
        "agreement_with_deposit": summaries,
    }, indent=2) + "\n", encoding="utf-8")

    agree = sum(s["agrees"] for s in summaries)
    print(f"\n  RECONSTRUCTION, {len(dirs)} experiments -> {len(all_recs)} DERIVED records")
    print(f"  -> {a.out}")
    print(f"  -> {a.summary}\n")
    print(f"  {'exp':7}{'reported BA':>13}{'recomputed':>13}{'diff':>10}"
          f"{'perfold AP':>12}{'pooled AP':>11}")
    for s in summaries:
        print(f"  {s['experiment']:7}{s['reported_balanced_accuracy']:13.9f}"
              f"{s['recomputed_balanced_accuracy']:13.9f}"
              f"{s['absolute_difference']:10.1e}"
              f"{s['per_fold_mean_average_precision']:12.4f}"
              f"{s['pooled_average_precision']:11.4f}")
    print(f"\n  {agree} of {len(summaries)} reported balanced accuracies reproduce "
          f"to better than 1e-12.")
    print(f"  Per-fold and pooled average precision are different quantities and both")
    print(f"  are in the provenance file, with the score-scale caveat, rather than one")
    print(f"  of them being chosen.\n")
    print(f"  {len(ASSUMPTIONS)} assumptions, all recorded in the provenance file.")
    print(f"  Every record carries derived: true and its fold relationship.\n")
    if agree != len(summaries):
        raise SystemExit("  NOT all balanced accuracies reproduce. "
                         "The reconstruction does not match the deposit.\n")


if __name__ == "__main__":
    main()
