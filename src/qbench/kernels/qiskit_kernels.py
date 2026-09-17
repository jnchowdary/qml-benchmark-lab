"""Qiskit fidelity quantum kernels.

Verified against qiskit 2.4.2 / qiskit-machine-learning 0.9.1 on 2026-09-17.

NOTE ON THE API: the plan's first draft used the `ZZFeatureMap` CLASS, which
emits a DeprecationWarning on qiskit >= 2.1 and is scheduled for removal. This
module uses the `zz_feature_map` FUNCTION form instead. If you copy snippets
from the plan doc, take them from here rather than from section 6.

Measured cost on a 4-qubit, reps=2 map with StatevectorSampler:
~9.0 ms per kernel entry, flat across n=10..60 (so cost is n^2/2 * 9ms).
Budget from that, not from optimism:
    n=100  ->    4,950 entries ->  ~45 s
    n=250  ->   31,125 entries ->  ~4.7 min
    n=500  ->  124,750 entries ->  ~19 min   per kernel matrix
"""

from __future__ import annotations

import numpy as np
from qiskit.circuit.library import z_feature_map, zz_feature_map
from qiskit.primitives import StatevectorSampler
from qiskit_machine_learning.kernels import FidelityQuantumKernel
from qiskit_machine_learning.state_fidelities import ComputeUncompute

__all__ = ["build_qiskit_kernel", "qiskit_param_grid", "MS_PER_ENTRY_4Q", "estimate_build_seconds"]

# Measured on this project's reference container, 4 qubits, reps=2. Re-measure
# on the real machine before trusting any schedule that depends on it.
MS_PER_ENTRY_4Q = 9.0


def build_qiskit_kernel(
    n_qubits: int,
    reps: int = 2,
    entanglement: str = "linear",
    feature_map: str = "zz",
):
    """Fidelity quantum kernel over `n_qubits` qubits.

    Input contract: X has shape (n_samples, n_qubits) -- one feature per qubit,
    already reduced by the mapping strategy in features.py and scaled into
    roughly [0, pi). Feeding unscaled features produces a kernel that looks
    fine (unit diagonal, PSD) but encodes nothing, which is the single easiest
    way to waste a week of compute here.

    Returns an object with .evaluate(x_vec, y_vec=None) -> ndarray.
    """
    if feature_map == "zz":
        fm = zz_feature_map(feature_dimension=n_qubits, reps=reps, entanglement=entanglement)
    elif feature_map == "z":
        fm = z_feature_map(feature_dimension=n_qubits, reps=reps)
    else:
        raise ValueError(f"Unknown feature_map {feature_map!r}; expected 'zz' or 'z'")

    fidelity = ComputeUncompute(sampler=StatevectorSampler())
    return FidelityQuantumKernel(feature_map=fm, fidelity=fidelity)


def qiskit_param_grid() -> list[dict]:
    """Structural grid. Pre-screen with g(K_C||K_Q) on one seed before running
    all of these across 10 seeds -- see section 7 of the plan."""
    return [
        {"feature_map": fm, "reps": r, "entanglement": e}
        for fm in ("zz",)
        for r in (1, 2, 3)
        for e in ("linear", "full")
    ] + [{"feature_map": "z", "reps": r, "entanglement": "linear"} for r in (1, 2)]


def estimate_build_seconds(n: int, ms_per_entry: float = MS_PER_ENTRY_4Q) -> float:
    """Wall-clock estimate for an n x n kernel build. Use it to refuse a
    configuration before it eats the afternoon, not to explain afterwards."""
    entries = n * (n - 1) / 2
    return entries * ms_per_entry / 1000.0
