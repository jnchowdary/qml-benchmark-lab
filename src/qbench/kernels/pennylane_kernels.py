"""PennyLane embedding kernels.

Verified against pennylane 0.45.1 on 2026-09-17.

A MEASURED CONFOUND YOU MUST NOT IGNORE
---------------------------------------
On the same 4-qubit workload, measured here:
    Qiskit  FidelityQuantumKernel + StatevectorSampler : ~9.0 ms / entry
    PennyLane default.qubit + adjoint embedding        : ~2.2 ms / entry
That is a ~4x gap from FRAMEWORK OVERHEAD, not from anything about the kernels.

Consequences for section 9's runtime-scaling plot:
  - Never compare "quantum kernel A (Qiskit)" against "quantum kernel B
    (PennyLane)" on wall-clock and call it a property of the kernels.
  - Either implement every compared kernel in ONE framework, or report
    circuit-evaluation COUNTS (framework-independent) as the cost metric and
    keep wall-clock as a secondary, explicitly framework-labelled number.
  - The honest headline cost metric for this project is circuit evaluations.
"""

from __future__ import annotations

import numpy as np
import pennylane as qml

__all__ = ["build_pennylane_kernel", "pennylane_param_grid", "available_devices",
           "DEFAULT_DEVICE", "MS_PER_ENTRY_4Q"]

# Measured on this project's reference container, 4 qubits, angle embedding.
# This is a CONTAINER number and is not the schedule. scripts/benchmark_backends.py
# re-measures on the machine that will actually run the experiments; the figure
# recorded in docs/ from that run is the one any timetable must use.
MS_PER_ENTRY_4Q = 2.2

_EMBEDDINGS = ("angle", "iqp")

# lightning.qubit is a compiled C++ statevector simulator and is usually several
# times faster than default.qubit for this workload, but it is a separate
# package (pennylane-lightning) and may not be installed. The name is a
# parameter so the choice is recorded in the run metadata rather than being an
# invisible property of whichever machine happened to run the job.
DEFAULT_DEVICE = "default.qubit"


def available_devices(candidates=("lightning.gpu", "lightning.qubit", "default.qubit"), wires=2):
    """Device names that can actually be instantiated here, fastest first.

    Import-time availability is not the test; instantiation is. A
    pennylane-lightning install that does not match the local architecture
    imports cleanly and then fails to build a device.
    """
    ok = []
    for name in candidates:
        try:
            qml.device(name, wires=wires)
        except Exception:  # noqa: BLE001 - any failure means "not usable here"
            continue
        ok.append(name)
    return ok


def build_pennylane_kernel(n_qubits: int, embedding: str = "angle", reps: int = 1,
                           device: str = DEFAULT_DEVICE):
    """Return an object exposing .evaluate(x_vec, y_vec=None) -> Gram matrix.

    Deliberately mirrors the Qiskit kernel's interface so models.py and
    tuning.py never branch on which framework produced a kernel.

    Input contract: X shape (n_samples, n_qubits), scaled into roughly [0, pi).

    `device` selects the simulator. It changes wall-clock only: every device
    here is an exact statevector simulator, so the Gram matrices must agree to
    floating-point tolerance. tests/test_kernel_properties.py asserts that,
    because a "faster backend" that quietly changes the numbers is worse than
    a slow one.
    """
    if embedding not in _EMBEDDINGS:
        raise ValueError(f"Unknown embedding {embedding!r}; expected one of {_EMBEDDINGS}")

    dev = qml.device(device, wires=n_qubits)

    def _embed(x):
        if embedding == "angle":
            for _ in range(reps):
                qml.AngleEmbedding(x, wires=range(n_qubits))
        else:  # iqp
            qml.IQPEmbedding(x, wires=range(n_qubits), n_repeats=reps)

    @qml.qnode(dev)
    def _overlap(x1, x2):
        _embed(x1)
        qml.adjoint(_embed)(x2)
        return qml.probs(wires=range(n_qubits))

    class _PennyLaneKernel:
        """Matches FidelityQuantumKernel's surface, not its internals."""

        n_evaluations = 0
        device_name = device
        config = {"embedding": embedding, "reps": reps, "n_qubits": n_qubits, "device": device}

        def _k(self, a, b):
            type(self).n_evaluations += 1
            return float(_overlap(a, b)[0])

        def evaluate(self, x_vec, y_vec=None):
            x_vec = np.asarray(x_vec, dtype=float)
            if y_vec is None:
                return np.asarray(qml.kernels.square_kernel_matrix(x_vec, self._k), dtype=float)
            y_vec = np.asarray(y_vec, dtype=float)
            return np.asarray(qml.kernels.kernel_matrix(x_vec, y_vec, self._k), dtype=float)

    return _PennyLaneKernel()


def pennylane_param_grid() -> list[dict]:
    return [
        {"embedding": e, "reps": r}
        for e in _EMBEDDINGS
        for r in (1, 2)
    ]
