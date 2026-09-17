"""Classical kernel baselines.

Every builder returns a callable producing a Gram matrix, so classical and
quantum kernels share one interface and one code path through
SVC(kernel='precomputed'). That symmetry is what makes the paired statistical
tests in section 9 of the plan valid: identical folds, identical solver,
only the kernel differs.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics.pairwise import linear_kernel, polynomial_kernel, rbf_kernel

__all__ = ["CLASSICAL_KERNELS", "build_classical_kernel", "classical_param_grid"]


def build_classical_kernel(name: str, **params):
    """Return fn(X, Y=None) -> Gram matrix for the named classical kernel.

    Parameters
    ----------
    name : {"linear", "rbf", "poly"}
    params : kernel hyperparameters (gamma, degree, coef0)
    """
    if name == "linear":
        return lambda X, Y=None: linear_kernel(X, X if Y is None else Y)
    if name == "rbf":
        gamma = params.get("gamma", None)
        return lambda X, Y=None: rbf_kernel(X, X if Y is None else Y, gamma=gamma)
    if name == "poly":
        degree = params.get("degree", 3)
        gamma = params.get("gamma", None)
        coef0 = params.get("coef0", 1.0)
        return lambda X, Y=None: polynomial_kernel(
            X, X if Y is None else Y, degree=degree, gamma=gamma, coef0=coef0
        )
    raise ValueError(f"Unknown classical kernel {name!r}; expected one of {CLASSICAL_KERNELS}")


CLASSICAL_KERNELS = ("linear", "rbf", "poly")


def classical_param_grid(name: str) -> list[dict]:
    """Structural grid per kernel. C is tuned separately against the
    precomputed Gram matrix, so it does not appear here."""
    if name == "linear":
        return [{}]
    if name == "rbf":
        return [{"gamma": g} for g in ("scale", 1e-3, 1e-2, 1e-1, 1.0)]
    if name == "poly":
        return [{"degree": d, "gamma": "scale"} for d in (2, 3, 4)]
    raise ValueError(f"Unknown classical kernel {name!r}")


def best_classical_gram(X, grams: dict[str, np.ndarray], y=None) -> tuple[str, np.ndarray]:
    """Pick the reference classical kernel that g(K_C||K_Q) is measured against.

    Section 6 of the plan compares the quantum kernel to "the best classical
    kernel". That choice must be made on TRAINING data only and recorded, or g
    is computed against a test-informed baseline and the whole comparison leaks.
    Selection by kernel-target alignment, which needs no fitted model.
    """
    if y is None:
        raise ValueError("Kernel-target alignment needs labels; pass training y only.")
    y = np.asarray(y, dtype=float)
    y_signed = np.where(y > 0, 1.0, -1.0)
    ideal = np.outer(y_signed, y_signed)
    best_name, best_score = None, -np.inf
    for name, K in grams.items():
        score = float(
            np.sum(K * ideal) / (np.linalg.norm(K, "fro") * np.linalg.norm(ideal, "fro"))
        )
        if score > best_score:
            best_name, best_score = name, score
    return best_name, grams[best_name]
