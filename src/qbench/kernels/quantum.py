"""The frozen quantum kernel grid, and a Gram cache that makes it affordable.

THE FROZEN GRID
---------------
Four structural settings, declared in docs/pre-registration.md section 3 and
not changeable without a logged deviation: angle and IQP embeddings, each at
one and two repetitions, on `lightning.qubit`.

All four are run. An earlier design used the geometric difference to screen
them down to three, which is circular: conditioning the experiment on g and
then testing whether g predicts the outcome cannot answer the question.

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

from .pennylane_kernels import DEFAULT_DEVICE, build_pennylane_kernel

__all__ = [
    "FROZEN_SETTINGS",
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


def setting_label(params) -> str:
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
        self._cache: dict = {}
        self._kernels: dict = {}
        self._evaluations = 0
        self._hits = 0

    def _kernel(self, params):
        key = setting_label(params)
        if key not in self._kernels:
            self._kernels[key] = build_pennylane_kernel(
                self.n_qubits, embedding=params["embedding"],
                reps=params["reps"], device=self.device)
        return self._kernels[key]

    def gram_fn(self, params):
        label = setting_label(params)

        def compute(X, Y=None):
            key = (label, _fingerprint(X), None if Y is None else _fingerprint(Y))
            if key in self._cache:
                self._hits += 1
                return self._cache[key]
            X = np.asarray(X, dtype=float)
            n = len(X)
            if Y is None:
                self._evaluations += n * (n - 1) // 2
                K = np.asarray(self._kernel(params).evaluate(X), dtype=float)
            else:
                Y = np.asarray(Y, dtype=float)
                self._evaluations += n * len(Y)
                K = np.asarray(self._kernel(params).evaluate(X, Y), dtype=float)
            self._cache[key] = K
            return K

        return compute

    def evaluations(self) -> int:
        """Circuit evaluations actually performed. Cache hits are not counted,
        because the cache is an implementation detail and the reported cost
        must be what the experiment costs, not what this run happened to save."""
        return self._evaluations

    def cache_hits(self) -> int:
        return self._hits

    def clear(self) -> None:
        """Drop cached Gram matrices, keeping the counters and the compiled
        circuits. Called between cells so memory does not grow across a run
        that spans several nights."""
        self._cache.clear()
