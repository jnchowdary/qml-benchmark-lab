"""The frozen quantum kernel grid, and a Gram cache that makes it affordable.

THE FROZEN GRID
---------------
Four structural settings, declared in docs/pre-registration.md section 3 and
not changeable without a logged deviation: angle and IQP embeddings, each at
one and two repetitions, on `lightning.qubit`.

All four are run. An earlier design used the geometric difference to screen
them down to three, which is circular: conditioning the experiment on g and
then testing whether g predicts the outcome cannot answer the question.

BANDWIDTH, AND WHY IT IS NOT PART OF THE REGISTRATION
------------------------------------------------------
The registered grid tunes embedding family, repetitions and C. It does not
tune bandwidth: `features.scale_to_angles` fixes the range at [0, pi] and
nothing varies it. The classical arm meanwhile tunes RBF gamma over eleven
values spanning five decades. That asymmetry is not the declared search-size
asymmetry of pre-registration section 9, which is about grid point counts and
inner-CV optimism; it is a shape parameter the quantum arm cannot vary at all,
and bandwidth is the parameter the recent literature identifies as deciding
whether a fidelity kernel works past a handful of qubits.

The registered results themselves say the grid stops on the wrong side of a
boundary. `reps` is a bandwidth knob in disguise for the angle family, since
two applications of AngleEmbedding is one application at twice the angle, and
across both datasets, all three training sizes and both embedding families the
SMALLER effective scale won twelve times out of twelve, monotonically. The
registered grid contains scale factors 1 and 2 and no value below 1.

So `BANDWIDTH_GRID` exists, and it is EXPLORATORY. It was added after the
registered sweep was seen, which makes any result from it post-hoc, and
docs/deviations.md D4 records that and fixes in advance what it may conclude.
The registered path is untouched: bandwidth 1.0 is the registered kernel, and
a test asserts the registered settings still produce identical Gram matrices.

HOW THE GRAM IS COMPUTED, AND WHY IT IS NOT WHAT IT COSTS
---------------------------------------------------------
A fidelity kernel is K_ij = |<phi(x_i)|phi(x_j)>|^2. The textbook protocol,
and the only one available on hardware, runs U(x_i)^dagger U(x_j) and measures
the all-zeros probability, once per PAIR: n(n-1)/2 circuit evaluations.

On a simulator the statevectors can be extracted directly, so n executions and
one matrix product give the whole Gram. Measured 25 Sep 2026: 16 to 46 times
faster at 40 points, agreeing with the pairwise protocol to 1e-15, and the
advantage grows with n because one method is O(n) and the other O(n^2). It
turned a projected 110-hour sweep into well under an hour.

This changes no number. It changes what the run costs on THIS machine, and
nothing about what the experiment would cost on hardware. So `evaluations()`
keeps reporting the hardware-equivalent n(n-1)/2, which is what the
pre-registration commits to reporting, and `simulator_executions()` reports
the shortcut separately. Conflating the two would let the paper claim quantum
kernels are cheap on the strength of something no quantum computer can do.

WHY THE CACHE EXISTS
--------------------
`qbench.tuning` was written for classical kernels, where recomputing a Gram
matrix is free. It computes the training Gram once per structural setting in
`select_hyperparameters`, and then `evaluate` recomputes the training Gram for
the setting that won, plus the test Gram. Classically that second training Gram
costs microseconds. Here it costs about 30 seconds, and a fallback to a
second-choice setting costs another.

Over the full sweep that duplicate is roughly 600 extra training Gram matrices,
about six hours of the run, computing numbers already in memory. The cache
removes it without touching `tuning.py`, so the classical and quantum paths
stay identical in every respect that affects a result.

Entries are keyed by the content of the input arrays, not their identity, so a
re-derived but equal array still hits. `clear()` is called between cells to
bound memory: four settings times two matrices at 350 points is about 8 MB.

COST ACCOUNTING
---------------
The pre-registration reports cost in circuit evaluations, which are
framework-independent, with wall-clock as a secondary always labelled by
backend. `evaluations()` reports the true count, excluding cache hits, so the
figure is what the experiment would cost on hardware rather than what this
particular optimisation happened to save.
"""

from __future__ import annotations

import hashlib

import numpy as np

import pennylane as qml

from .pennylane_kernels import DEFAULT_DEVICE

__all__ = [
    "FROZEN_SETTINGS",
    "BANDWIDTH_GRID",
    "REGISTERED_BANDWIDTH",
    "bandwidth_grid_for",
    "QuantumGramFactory",
    "setting_label",
    "expected_entries",
    "entries_without_cache",
]

# docs/pre-registration.md section 3. Do not edit without a deviation record.
FROZEN_SETTINGS = (
    {"embedding": "angle", "reps": 1},
    {"embedding": "angle", "reps": 2},
    {"embedding": "iqp", "reps": 1},
    {"embedding": "iqp", "reps": 2},
)

# The registered grid has no bandwidth: `scale_to_angles` fixes the feature
# range at [0, pi] and nothing varies it. A bandwidth of 1.0 IS the registered
# kernel, exactly, and every registered record is reproduced by it. See
# docs/deviations.md D4 for why an exploratory arm with other values exists and
# what it is and is not allowed to conclude.
REGISTERED_BANDWIDTH = 1.0

# Powers of two around the registered value, so the registered kernel is nested
# inside the grid rather than sitting beside it. Chosen before any bandwidth
# result was computed, and frozen in D4.
#
# The range is set by where concentration bites, not by taste. For a product
# angle kernel on n qubits the Gram concentrates when the per-qubit fidelity
# falls much below exp(-1/n); at 12 qubits with typical angle gaps near pi/2
# that puts the interesting region around 0.1 to 0.5, and at 4 qubits much
# higher. 0.0625 to 4.0 brackets both ends with room to spare, and the grid is
# wide enough that a selected value on its boundary is itself informative.
BANDWIDTH_GRID = (0.0625, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0)


def bandwidth_grid_for(params, grid=BANDWIDTH_GRID) -> list[dict]:
    """One structural setting expanded into a bandwidth grid.

    This is the shape that makes the two arms symmetric. On the classical side
    a kernel FAMILY is one record and its shape parameter (RBF gamma, poly
    degree) is chosen by inner CV inside it. Registered as it stands, the
    quantum side has a family per record and no shape parameter at all, so the
    classical arm tunes bandwidth over eleven values and the quantum arm over
    none. Expanding here, rather than adding settings to the sweep, keeps one
    record per embedding family and lets `select_hyperparameters` choose the
    bandwidth on training folds exactly as it chooses gamma.
    """
    return [{**params, "bandwidth": float(b)} for b in grid]


def setting_label(params) -> str:
    """Stable label for a structural setting.

    Backwards compatible on purpose: at the registered bandwidth the label is
    the one already written into every record of the registered sweep, so
    resume keys, cache keys and `primary_tests.py` all keep working and the
    registered files are never reinterpreted.
    """
    base = f"{params['embedding']}-r{params['reps']}"
    bw = float(params.get("bandwidth", REGISTERED_BANDWIDTH))
    return base if bw == REGISTERED_BANDWIDTH else f"{base}-b{bw:g}"


def circuit_label(params) -> str:
    """Identity of the CIRCUIT, which bandwidth does not change.

    Bandwidth scales the data going in, not the gates, so all bandwidths of one
    embedding family share a QNode and a device.
    """
    return f"{params['embedding']}-r{params['reps']}"


def _fingerprint(a) -> str:
    a = np.ascontiguousarray(np.asarray(a, dtype=float))
    return hashlib.sha256(a.tobytes() + str(a.shape).encode()).hexdigest()[:16]


def expected_entries(n_train: int, n_test: int) -> int:
    """Circuit evaluations for ONE structural setting, one cell, one seed, with
    the cache in place.

    One training Gram (n_train(n_train-1)/2 entries: the matrix is symmetric
    and its diagonal is 1) plus one test block (n_test x n_train).

    Each setting goes through its own `tune_and_evaluate`, because the
    pre-registration promises a per-setting comparison as well as
    best-of-four, so each needs its own test block. The cache does not change
    that; what it removes is the SECOND training Gram that `evaluate`
    recomputes after selection. See `entries_without_cache`.
    """
    return n_train * (n_train - 1) // 2 + n_test * n_train


def entries_without_cache(n_train: int, n_test: int) -> int:
    """What the same work costs if `evaluate` recomputes the training Gram.

    `tuning.evaluate` calls the kernel again on the full training set after
    selection. Classically that is microseconds; here it is a whole extra
    training Gram per setting, which is 35% of the sweep.
    """
    return 2 * (n_train * (n_train - 1) // 2) + n_test * n_train


class QuantumGramFactory:
    """gram_fn for qbench.tuning, with a content-keyed Gram cache.

    Usage mirrors the classical path exactly:

        factory = QuantumGramFactory(n_qubits=8)
        tune_and_evaluate("quantum", factory.gram_fn, FROZEN_SETTINGS, ...)

    so `tuning.py` cannot tell the two apart, which is the property that makes
    the paired tests valid.
    """

    def __init__(self, n_qubits: int, device: str = DEFAULT_DEVICE):
        self.n_qubits = int(n_qubits)
        self.device = device
        self._states_cache: dict = {}
        self._counted: set = set()
        self._kernels: dict = {}
        self._evaluations = 0
        self._simulator_executions = 0
        self._hits = 0

    def _states_fn(self, params):
        """QNode returning the embedded statevector for one point."""
        key = circuit_label(params)
        if key not in self._kernels:
            nq, embedding, reps = self.n_qubits, params["embedding"], params["reps"]
            dev = qml.device(self.device, wires=nq)

            def embed(x):
                if embedding == "angle":
                    for _ in range(reps):
                        qml.AngleEmbedding(x, wires=range(nq))
                else:
                    qml.IQPEmbedding(x, wires=range(nq), n_repeats=reps)

            @qml.qnode(dev)
            def psi(x):
                embed(x)
                return qml.state()

            self._kernels[key] = psi
        return self._kernels[key]

    def _states(self, params, X):
        """Statevectors for X, cached by content.

        Caching STATES rather than Gram matrices is what makes the test block
        nearly free: it reuses the training states already computed for the
        training Gram, so a cell costs n_train + n_test executions instead of
        n_train(n_train-1)/2 + n_test*n_train.

        Bandwidth scales the data on the way into the circuit, so it is part of
        the cache key via `setting_label`: two bandwidths are two different
        kernels and must never share cached states.
        """
        key = (setting_label(params), _fingerprint(X))
        if key in self._states_cache:
            return self._states_cache[key]
        psi = self._states_fn(params)
        bw = float(params.get("bandwidth", REGISTERED_BANDWIDTH))
        A = np.stack([np.asarray(psi(x)) for x in np.asarray(X, dtype=float) * bw])
        self._simulator_executions += len(A)
        self._states_cache[key] = A
        return A

    def gram_fn(self, params):
        label = setting_label(params)

        def compute(X, Y=None):
            # Hardware-equivalent cost is charged ONCE per distinct Gram the
            # experiment needs, not once per call: asking for the same matrix
            # twice does not make the experiment more expensive to run on a
            # quantum computer.
            gram_key = (label, _fingerprint(X), None if Y is None else _fingerprint(Y))
            first_time = gram_key not in self._counted
            if not first_time:
                self._hits += 1
            self._counted.add(gram_key)

            A = self._states(params, X)
            n = len(A)
            if Y is None:
                if first_time:
                    self._evaluations += n * (n - 1) // 2   # hardware-equivalent cost
                K = np.abs(A.conj() @ A.T) ** 2
                K = (K + K.T) / 2                          # kill 1e-16 asymmetry
                np.fill_diagonal(K, 1.0)
            else:
                B = self._states(params, Y)
                if first_time:
                    self._evaluations += n * len(B)
                K = np.abs(A.conj() @ B.T) ** 2
            return np.clip(np.real(K), 0.0, 1.0)

        return compute

    def evaluations(self) -> int:
        """Circuit evaluations actually performed. Cache hits are not counted,
        because the cache is an implementation detail and the reported cost
        must be what the experiment costs, not what this run happened to save."""
        return self._evaluations

    def simulator_executions(self) -> int:
        """Circuits actually simulated. Much smaller than `evaluations()`, and
        reported separately so nobody mistakes a simulator shortcut for a
        property of quantum kernels."""
        return self._simulator_executions

    def cache_hits(self) -> int:
        return self._hits

    def clear(self) -> None:
        """Drop cached statevectors, keeping the counters and the QNodes.
        Called between cells so memory does not grow across a long run: 350
        states at 12 qubits is about 22 MB per setting."""
        self._states_cache.clear()
        self._counted.clear()
