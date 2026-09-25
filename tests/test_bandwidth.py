"""The exploratory bandwidth arm, and proof it does not touch the registration.

WHY THIS FILE EXISTS
--------------------
Adding a hyperparameter to the quantum kernel after the registered sweep has
already run is the single most dangerous edit in this project. Two things can
go wrong and neither raises an exception:

  1. The registered kernel changes. If bandwidth 1.0 is not EXACTLY the kernel
     the registered sweep used, then 7,200 records and the H1 verdict are
     silently invalidated, and the only symptom is numbers that drift.
  2. The bandwidth does not actually reach the circuit, or reaches it in the
     wrong place, and the whole arm measures nothing while looking fine. A
     bandwidth that is accepted, recorded, and ignored would produce seven
     identical Gram matrices and an inner-CV winner chosen by tie-breaking.

Both are tested here directly rather than inferred from a passing sweep.

The angle family gives a free oracle for the second one. Two applications of
AngleEmbedding is one application at twice the angle, so angle-r1 at bandwidth
2b must equal angle-r2 at bandwidth b, exactly, for every b. If the bandwidth
plumbing is wrong that identity breaks. It does not hold for IQP, whose
repetitions also repeat entangling terms, so it is asserted only where it is
true.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qbench.kernels.quantum import (  # noqa: E402
    BANDWIDTH_GRID,
    FROZEN_SETTINGS,
    REGISTERED_BANDWIDTH,
    QuantumGramFactory,
    bandwidth_grid_for,
    circuit_label,
    setting_label,
)


@pytest.fixture(scope="module")
def X():
    rng = np.random.default_rng(0)
    return rng.uniform(0.0, np.pi, size=(12, 4))


def gram(params, X, Y=None, n_qubits=4):
    return QuantumGramFactory(n_qubits).gram_fn(params)(X, Y)


# ------------------------------------------- the registered path is untouched

@pytest.mark.parametrize("params", FROZEN_SETTINGS)
def test_registered_settings_are_bandwidth_one(params, X):
    """A frozen setting carries no bandwidth key, and must behave exactly as a
    bandwidth of 1.0. If these ever differ, every registered record is void."""
    a = gram(dict(params), X)
    b = gram({**params, "bandwidth": REGISTERED_BANDWIDTH}, X)
    assert np.array_equal(a, b)


@pytest.mark.parametrize("params", FROZEN_SETTINGS)
def test_registered_labels_are_unchanged(params):
    """Resume keys, cache keys and every stored record use these strings. A new
    label format at the registered bandwidth would orphan 7,200 records."""
    assert setting_label(dict(params)) == f"{params['embedding']}-r{params['reps']}"
    assert setting_label({**params, "bandwidth": 1.0}) == setting_label(dict(params))


def test_registered_bandwidth_is_one():
    assert REGISTERED_BANDWIDTH == 1.0
    assert REGISTERED_BANDWIDTH in BANDWIDTH_GRID, (
        "the registered kernel must be nested inside the exploratory grid, so the "
        "arm can never beat it by searching somewhere it was not")


# ------------------------------------------------- the bandwidth does reach it

@pytest.mark.parametrize("bw", [b for b in BANDWIDTH_GRID if b != REGISTERED_BANDWIDTH])
def test_bandwidth_changes_the_kernel(bw, X):
    """A bandwidth that is recorded but ignored would make the whole arm
    meaningless while every test above still passes."""
    base = gram({"embedding": "angle", "reps": 1}, X)
    other = gram({"embedding": "angle", "reps": 1, "bandwidth": bw}, X)
    assert not np.allclose(base, other, atol=1e-9)


@pytest.mark.parametrize("bw", [0.0625, 0.25, 0.5, 1.0, 2.0])
def test_angle_reps_is_a_bandwidth_knob(bw, X):
    """angle-r1 at 2b equals angle-r2 at b. This is the oracle: it fixes both
    that bandwidth multiplies the data and that it does so in the right place.

    It is also the fact the whole exploratory arm rests on, since it is what
    makes the registered grid's `reps` parameter a bandwidth grid containing
    only the values 1 and 2 and nothing smaller.
    """
    one = gram({"embedding": "angle", "reps": 1, "bandwidth": 2 * bw}, X)
    two = gram({"embedding": "angle", "reps": 2, "bandwidth": bw}, X)
    assert np.allclose(one, two, atol=1e-12)


def test_iqp_reps_is_not_merely_a_bandwidth_knob(X):
    """Asserted so the oracle above is never generalised by mistake: IQP
    repetitions repeat entangling terms, so they are not a rescaling."""
    one = gram({"embedding": "iqp", "reps": 1, "bandwidth": 2.0}, X)
    two = gram({"embedding": "iqp", "reps": 2, "bandwidth": 1.0}, X)
    assert not np.allclose(one, two, atol=1e-6)


# --------------------------------------------------------- caching and labels

def test_distinct_bandwidths_never_share_cached_states(X):
    """The state cache is keyed by content plus label. If bandwidth were left
    out of that key, the second bandwidth would silently return the first
    bandwidth's states and every result would be the registered one."""
    f = QuantumGramFactory(4)
    p = {"embedding": "angle", "reps": 1}
    a = f.gram_fn({**p, "bandwidth": 0.25})(X)
    b = f.gram_fn({**p, "bandwidth": 1.0})(X)
    assert not np.allclose(a, b, atol=1e-9)
    assert len({k for k in f._states_cache}) == 2


def test_labels_are_unique_across_the_grid():
    labels = [setting_label(p) for s in FROZEN_SETTINGS for p in bandwidth_grid_for(s)]
    assert len(labels) == len(set(labels)) == len(FROZEN_SETTINGS) * len(BANDWIDTH_GRID)


def test_circuit_label_ignores_bandwidth():
    """All bandwidths of one family share a QNode: bandwidth scales the data,
    not the gates. Keying QNodes by the full label would build seven identical
    devices per family."""
    p = {"embedding": "iqp", "reps": 2}
    assert circuit_label({**p, "bandwidth": 0.25}) == circuit_label({**p, "bandwidth": 4.0})


def test_one_qnode_per_family_not_per_bandwidth(X):
    f = QuantumGramFactory(4)
    for bw in BANDWIDTH_GRID:
        f.gram_fn({"embedding": "angle", "reps": 1, "bandwidth": bw})(X)
    assert len(f._kernels) == 1


# --------------------------------------------------------------- grid shape

def test_grid_brackets_the_registered_value_on_both_sides():
    """A one-sided extension below 1.0 would be indistinguishable from choosing
    the direction that helps. The grid goes both ways."""
    assert min(BANDWIDTH_GRID) < REGISTERED_BANDWIDTH < max(BANDWIDTH_GRID)


def test_bandwidth_grid_for_preserves_the_family():
    grid = bandwidth_grid_for({"embedding": "iqp", "reps": 2})
    assert len(grid) == len(BANDWIDTH_GRID)
    assert all(g["embedding"] == "iqp" and g["reps"] == 2 for g in grid)
    assert sorted(g["bandwidth"] for g in grid) == sorted(BANDWIDTH_GRID)


# ------------------------------------------------- kernels stay well formed

@pytest.mark.parametrize("bw", BANDWIDTH_GRID)
def test_kernel_stays_a_valid_fidelity_kernel(bw, X):
    """Whatever the bandwidth, K must stay symmetric, unit-diagonal and in
    [0, 1]: it is a squared overlap. A scaling bug that wrapped angles past the
    Bloch sphere could still satisfy this, which is why the oracle above
    exists as well."""
    K = gram({"embedding": "angle", "reps": 1, "bandwidth": bw}, X)
    assert np.allclose(K, K.T, atol=1e-12)
    assert np.allclose(np.diag(K), 1.0, atol=1e-12)
    assert K.min() >= 0.0 and K.max() <= 1.0


def test_small_bandwidth_moves_toward_the_all_ones_kernel(X):
    """The failure mode at the far end of the grid, stated so it is recognised
    rather than mistaken for a result: as bandwidth goes to zero every point
    embeds to the same state and the kernel becomes trivially all-ones, which
    carries no information either. The grid has to be wide enough to show both
    pathologies."""
    tiny = gram({"embedding": "angle", "reps": 1, "bandwidth": 1e-4}, X)
    assert tiny.min() > 0.99
