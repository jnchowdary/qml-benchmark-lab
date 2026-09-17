"""End-to-end smoke test: data -> mapping -> angles -> kernels -> g -> SVM.

Asserts the pipeline RUNS and produces well-formed output. Deliberately does
not assert any particular metric value: this test must never be the thing that
tells you quantum won or lost.

Runs on the synthetic dataset so it needs no Kaggle credentials, and stays
small enough to run on every commit.
"""

import warnings

import numpy as np
import pytest
from sklearn.metrics import average_precision_score
from sklearn.svm import SVC

from qbench.data import balanced_subsample, load_dataset, make_split
from qbench.features import fit_mapping, scale_to_angles
from qbench.kernels.classical import best_classical_gram, build_classical_kernel
from qbench.kernels.geometric_difference import (
    g_lambda_sweep,
    geometric_difference_regularised,
    interpret_g,
    lambda_from_svm_C,
)
from qbench.kernels.pennylane_kernels import build_pennylane_kernel
from qbench.kernels.qiskit_kernels import build_qiskit_kernel

N_QUBITS = 3
N_PER_CLASS = 8


@pytest.fixture(scope="module")
def tiny_split():
    X, y, _ = load_dataset("synthetic")
    X, y = balanced_subsample(X, y, n_per_class=N_PER_CLASS, seed=0)
    return make_split(X, y, seed=0, test_size=0.375)


@pytest.fixture(scope="module")
def angles(tiny_split):
    X_train, X_test, y_train, y_test = tiny_split
    X_tr_mapped, transform = fit_mapping(X_train, y_train, N_QUBITS, "pca", seed=0)
    X_tr_ang, to_angles = scale_to_angles(X_tr_mapped, transform_fn=None)
    return X_tr_ang, to_angles(transform(X_test)), y_train, y_test


def test_angles_are_in_rotation_range(angles):
    X_tr, X_te, _, _ = angles
    for arr in (X_tr, X_te):
        assert arr.min() >= -1e-9 and arr.max() <= np.pi + 1e-9


@pytest.mark.parametrize(
    "builder",
    [
        pytest.param(lambda: build_qiskit_kernel(N_QUBITS, reps=1), id="qiskit-zz"),
        pytest.param(lambda: build_pennylane_kernel(N_QUBITS, "angle"), id="pl-angle"),
    ],
)
def test_end_to_end_quantum_svm(builder, angles):
    X_tr, X_te, y_tr, y_te = angles
    kernel = builder()

    K_tr = kernel.evaluate(x_vec=X_tr)
    K_te = kernel.evaluate(x_vec=X_te, y_vec=X_tr)
    assert K_tr.shape == (len(X_tr), len(X_tr))
    assert K_te.shape == (len(X_te), len(X_tr))

    model = SVC(kernel="precomputed", class_weight="balanced", C=1.0).fit(K_tr, y_tr)
    scores = model.decision_function(K_te)
    ap = average_precision_score(y_te, scores)

    assert np.isfinite(ap)
    assert 0.0 <= ap <= 1.0


def test_end_to_end_classical_svm(angles):
    X_tr, X_te, y_tr, y_te = angles
    kfn = build_classical_kernel("rbf")
    model = SVC(kernel="precomputed", class_weight="balanced", C=1.0).fit(kfn(X_tr), y_tr)
    ap = average_precision_score(y_te, model.decision_function(kfn(X_te, X_tr)))
    assert 0.0 <= ap <= 1.0


def test_geometric_difference_on_real_kernels(angles):
    """The pre-screen step of the protocol, wired end to end."""
    X_tr, _, y_tr, _ = angles
    grams = {n: build_classical_kernel(n)(X_tr) for n in ("linear", "rbf", "poly")}
    name, K_c = best_classical_gram(X_tr, grams, y=y_tr)
    assert name in grams

    K_q = build_qiskit_kernel(N_QUBITS, reps=1).evaluate(x_vec=X_tr)

    lam = lambda_from_svm_C(C=1.0, n=len(X_tr))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        g = geometric_difference_regularised(K_c, K_q, lam=lam)
    assert np.isfinite(g) and g > 0

    sweep = g_lambda_sweep(K_c, K_q)
    assert sweep["n"] == len(X_tr)
    assert set(sweep) >= {"g_by_lambda", "ceiling_sqrt_n", "cond_K_classical", "stable"}
    assert isinstance(interpret_g(g, len(X_tr)), str)


def test_results_record_has_required_keys(angles):
    """The run record shape section 8 depends on for every reported number."""
    X_tr, X_te, y_tr, y_te = angles
    kernel = build_qiskit_kernel(N_QUBITS, reps=1)
    K_tr = kernel.evaluate(x_vec=X_tr)
    model = SVC(kernel="precomputed", C=1.0).fit(K_tr, y_tr)
    record = {
        "dataset": "synthetic",
        "method": "qiskit-zz",
        "seed": 0,
        "n_qubits": N_QUBITS,
        "mapping": "pca",
        "backend": "statevector",
        "shots": None,
        "n_train": len(X_tr),
        "average_precision": float(
            average_precision_score(
                y_te, model.decision_function(kernel.evaluate(x_vec=X_te, y_vec=X_tr))
            )
        ),
    }
    required = {"dataset", "method", "seed", "n_qubits", "mapping", "backend", "shots"}
    assert required <= set(record)
    assert np.isfinite(record["average_precision"])
