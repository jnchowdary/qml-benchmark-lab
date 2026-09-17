#!/usr/bin/env python3
"""The reviewer-facing quick benchmark.

This is a SMOKE TEST AND DEMO, not evidence. It runs one dataset, a tiny
subsample, two seeds and fixed hyperparameters so a reviewer can confirm the
pipeline works end to end in minutes. No number printed here belongs in the
paper -- the paper's numbers come from run_full_benchmark.py.

Enforces its own wall-clock budget so the README's '<30 minutes' claim is a
tested property rather than a hope.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import yaml
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from sklearn.svm import SVC

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qbench.data import balanced_subsample, load_dataset, make_split  # noqa: E402
from qbench.features import fit_mapping, scale_to_angles  # noqa: E402
from qbench.kernels.classical import best_classical_gram, build_classical_kernel  # noqa: E402
from qbench.kernels.geometric_difference import (  # noqa: E402
    g_lambda_sweep,
    geometric_difference_regularised,
    interpret_g,
    lambda_from_svm_C,
)
from qbench.kernels.pennylane_kernels import build_pennylane_kernel  # noqa: E402
from qbench.kernels.qiskit_kernels import build_qiskit_kernel, estimate_build_seconds  # noqa: E402


def quantum_kernels(n_qubits):
    return {
        "qiskit-zz-r1": lambda: build_qiskit_kernel(n_qubits, reps=1),
        "qiskit-zz-r2": lambda: build_qiskit_kernel(n_qubits, reps=2),
        "pennylane-angle": lambda: build_pennylane_kernel(n_qubits, "angle"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/quick.yaml")
    ap.add_argument("--max-seconds", type=float, default=1800.0)
    ap.add_argument("--out", default="results/runs/quick")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    started = time.perf_counter()

    n_qubits = cfg["n_qubits"]
    n_per_class = cfg["n_per_class"]
    budget = estimate_build_seconds(2 * n_per_class) * len(quantum_kernels(n_qubits)) * len(cfg["seeds"])
    print(f"config: {args.config}")
    print(f"  dataset={cfg['dataset']} n_per_class={n_per_class} n_qubits={n_qubits} seeds={cfg['seeds']}")
    print(f"  estimated quantum kernel build time: {budget:.0f}s of {args.max_seconds:.0f}s budget\n")

    X_all, y_all, _ = load_dataset(cfg["dataset"])
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []

    for seed in cfg["seeds"]:
        X, y = balanced_subsample(X_all, y_all, n_per_class=n_per_class, seed=seed)
        X_tr, X_te, y_tr, y_te = make_split(X, y, seed=seed, test_size=cfg["test_size"])

        X_tr_m, transform = fit_mapping(X_tr, y_tr, n_qubits, cfg["mapping"], seed=seed)
        X_tr_a, to_angles = scale_to_angles(X_tr_m)
        X_te_a = to_angles(transform(X_te))

        # classical reference, selected on training data only
        grams = {n: build_classical_kernel(n)(X_tr_a) for n in ("linear", "rbf", "poly")}
        for name, K_tr in grams.items():
            K_te = build_classical_kernel(name)(X_te_a, X_tr_a)
            records.append(_evaluate(name, "classical", K_tr, K_te, y_tr, y_te, seed, cfg, None))
        ref_name, K_c = best_classical_gram(X_tr_a, grams, y=y_tr)

        lam = lambda_from_svm_C(C=cfg["C"], n=len(X_tr_a))
        for name, builder in quantum_kernels(n_qubits).items():
            kernel = builder()
            t0 = time.perf_counter()
            K_tr = kernel.evaluate(x_vec=X_tr_a)
            build_s = time.perf_counter() - t0
            K_te = kernel.evaluate(x_vec=X_te_a, y_vec=X_tr_a)

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                g = geometric_difference_regularised(K_c, K_tr, lam=lam)
                sweep = g_lambda_sweep(K_c, K_tr)
            rec = _evaluate(name, "quantum", K_tr, K_te, y_tr, y_te, seed, cfg, build_s)
            rec.update(
                g_vs_best_classical=g,
                g_lambda=lam,
                g_reference_kernel=ref_name,
                g_ceiling=sweep["ceiling_sqrt_n"],
                g_stable=sweep["stable"],
                cond_K_classical=sweep["cond_K_classical"],
            )
            records.append(rec)

    elapsed = time.perf_counter() - started
    (out_dir / "quick_results.json").write_text(json.dumps(records, indent=2))
    _report(records, elapsed, args.max_seconds)

    if elapsed > args.max_seconds:
        print(f"\nFAIL: {elapsed:.0f}s exceeds the {args.max_seconds:.0f}s budget.")
        return 1
    return 0


def _evaluate(name, family, K_tr, K_te, y_tr, y_te, seed, cfg, build_s):
    t0 = time.perf_counter()
    model = SVC(kernel="precomputed", C=cfg["C"], class_weight="balanced").fit(K_tr, y_tr)
    train_s = time.perf_counter() - t0
    scores = model.decision_function(K_te)
    preds = model.predict(K_te)
    return {
        "method": name,
        "family": family,
        "seed": seed,
        "dataset": cfg["dataset"],
        "n_qubits": cfg["n_qubits"],
        "mapping": cfg["mapping"],
        "backend": "statevector",
        "shots": None,
        "n_train": int(len(y_tr)),
        "average_precision": float(average_precision_score(y_te, scores)),
        "roc_auc": float(roc_auc_score(y_te, scores)),
        "f1": float(f1_score(y_te, preds, zero_division=0)),
        "kernel_build_time_s": build_s,
        "train_time_s": train_s,
    }


def _report(records, elapsed, budget):
    print(f"{'method':<18}{'family':<11}{'AP':>8}{'ROC-AUC':>9}{'F1':>7}{'build s':>9}{'g':>8}")
    print("-" * 70)
    by_method = {}
    for r in records:
        by_method.setdefault(r["method"], []).append(r)
    for method, rows in by_method.items():
        mean = lambda k: float(np.mean([r[k] for r in rows if r.get(k) is not None]))  # noqa: E731
        gs = [r["g_vs_best_classical"] for r in rows if "g_vs_best_classical" in r]
        g_str = f"{np.mean(gs):8.2f}" if gs else f"{'-':>8}"
        build = f"{mean('kernel_build_time_s'):9.2f}" if rows[0]["family"] == "quantum" else f"{'-':>9}"
        print(
            f"{method:<18}{rows[0]['family']:<11}{mean('average_precision'):8.3f}"
            f"{mean('roc_auc'):9.3f}{mean('f1'):7.3f}{build}{g_str}"
        )
    n = records[0]["n_train"]
    gs = [r["g_vs_best_classical"] for r in records if "g_vs_best_classical" in r]
    if gs:
        print(f"\n{interpret_g(float(np.mean(gs)), n)}")
    print(f"\nwall-clock {elapsed:.1f}s of {budget:.0f}s budget")
    print("NOT EVIDENCE: 2 seeds, fixed hyperparameters, tiny subsample. Demo only.")


if __name__ == "__main__":
    raise SystemExit(main())
