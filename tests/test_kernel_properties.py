"""Kernel property tests, run against every kernel builder in the project.

A fidelity kernel that is not symmetric, not PSD, or lacks a unit diagonal is
broken, and every SVM and every g value computed from it is meaningless. These
tests run on tiny inputs so they stay in CI at every commit.
"""

import numpy as np
import pytest

from qbench.kernels.classical import best_classical_gram, build_classical_kernel
from qbench.kernels.pennylane_kernels import build_pennylane_kernel
from qbench.kernels.qiskit_kernels import build_qiskit_kernel, estimate_build_seconds

N_QUBITS = 3
N_SAMPLES = 6


@pytest.fixture(scope="module")
def X():
    return np.random.default_rng(0).uniform(0, np.pi, (N_SAMPLES, N_QUBITS))


def quantum_builders():
    return [
        pytest.param(lambda: build_qiskit_kernel(N_QUBITS, reps=1), id="qiskit-zz"),
        pytest.param(lambda: build_qiskit_kernel(N_QUBITS, reps=1, feature_map="z"), id="qiskit-z"),
        pytest.param(lambda: build_pennylane_kernel(N_QUBITS, "angle"), id="pl-angle"),
        pytest.param(lambda: build_pennylane_kernel(N_QUBITS, "iqp"), id="pl-iqp"),
    ]


@pytest.mark.parametrize("builder", quantum_builders())
def test_quantum_kernel_symmetric(builder, X):
    K = builder().evaluate(x_vec=X)
    assert np.allclose(K, K.T, atol=1e-8)


@pytest.mark.parametrize("builder", quantum_builders())
def test_quantum_kernel_psd(builder, X):
    K = builder().evaluate(x_vec=X)
    assert np.linalg.eigvalsh(K).min() > -1e-6


@pytest.mark.parametrize("builder", quantum_builders())
def test_quantum_kernel_unit_diagonal(builder, X):
    """Fidelity kernels satisfy k(x,x) = 1. A diagonal that is not 1 means the
    overlap circuit is wired wrong."""
    K = builder().evaluate(x_vec=X)
    assert np.allclose(np.diag(K), 1.0, atol=1e-6)


@pytest.mark.parametrize("builder", quantum_builders())
def test_quantum_kernel_bounded(builder, X):
    K = builder().evaluate(x_vec=X)
    assert K.min() >= -1e-8 and K.max() <= 1.0 + 1e-8


@pytest.mark.parametrize("builder", quantum_builders())
def test_rectangular_test_kernel_shape(builder, X):
    """K_test must be (n_test, n_train) for SVC(kernel='precomputed')."""
    kernel = builder()
    X_test = X[:2]
    K = kernel.evaluate(x_vec=X_test, y_vec=X)
    assert K.shape == (2, N_SAMPLES)


@pytest.mark.parametrize("name", ["linear", "rbf", "poly"])
def test_classical_kernels_symmetric_psd(name, X):
    K = build_classical_kernel(name)(X)
    assert np.allclose(K, K.T, atol=1e-8)
    assert np.linalg.eigvalsh(K).min() > -1e-6


def test_unknown_classical_kernel_raises():
    with pytest.raises(ValueError, match="Unknown classical kernel"):
        build_classical_kernel("sigmoid-ish")


def test_best_classical_gram_requires_labels(X):
    grams = {n: build_classical_kernel(n)(X) for n in ("linear", "rbf")}
    with pytest.raises(ValueError, match="needs labels"):
        best_classical_gram(X, grams, y=None)


def test_best_classical_gram_picks_aligned_kernel(X):
    y = np.array([0, 0, 0, 1, 1, 1])
    grams = {n: build_classical_kernel(n)(X) for n in ("linear", "rbf", "poly")}
    name, K = grams and best_classical_gram(X, grams, y=y)
    assert name in grams
    assert K.shape == (N_SAMPLES, N_SAMPLES)


def test_build_estimate_is_quadratic():
    """Guards the budget arithmetic the schedule depends on."""
    assert estimate_build_seconds(200) / estimate_build_seconds(100) == pytest.approx(4.0, rel=0.02)
