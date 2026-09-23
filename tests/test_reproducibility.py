"""Determinism and reproducibility tests.

WHY THIS FILE EXISTS
--------------------
On 17 Sep 2026 the same diagnostic, run twice on identical data with an
identical seed, scored PR-AUC 0.5199 then 0.5664 on the churn dataset at k=4.
The cause was `SelectKBest(mutual_info_classif, ...)` in features.py:
mutual_info_classif adds random noise to break ties among continuous features,
governed by a `random_state` argument that defaulted to None because there was
no obvious place to thread the seed through a bare function reference.

The 75-test suite at the time passed. It never called fit_mapping, so
features.py sat at 62% coverage with the mapping functions uncovered.

Week 2's acceptance criterion is that two runs of the same seed produce
byte-identical splits. These tests are that criterion, executable.

Everything here runs on the synthetic dataset so CI needs no Kaggle account.
"""

import numpy as np
import pytest

from qbench.data import SEEDS, balanced_subsample, load_dataset, make_split
from qbench.features import MAPPINGS, fit_mapping, scale_to_angles

SEED = 0
N_QUBITS = 4


@pytest.fixture(scope="module")
def data():
    X, y, _ = load_dataset("synthetic")
    return X, y


@pytest.fixture(scope="module")
def split(data):
    X, y = data
    return make_split(X, y, seed=SEED)


# --- splits -------------------------------------------------------------------

def test_split_is_bit_identical_across_calls(data):
    """Week 2's acceptance criterion."""
    X, y = data
    a = make_split(X, y, seed=SEED)
    b = make_split(X, y, seed=SEED)
    for arr_a, arr_b in zip(a, b):
        assert np.array_equal(arr_a, arr_b)


def test_different_seeds_give_different_splits(data):
    """Guards the opposite failure: a seed that is silently ignored would make
    every 'reproducible' test above pass while destroying the 10-seed design."""
    X, y = data
    a = make_split(X, y, seed=0)
    b = make_split(X, y, seed=1)
    assert not np.array_equal(a[0], b[0])


def test_split_preserves_stratification(data):
    X, y = data
    _, _, y_tr, y_te = make_split(X, y, seed=SEED, test_size=0.3)
    assert abs(y_tr.mean() - y_te.mean()) < 0.05


def test_seeds_list_is_the_documented_twenty():
    """Widened from 10 on 23 Sep 2026 after the power analysis; see data.py."""
    assert SEEDS == list(range(20))


def test_the_original_ten_seeds_are_still_a_prefix():
    """Week-3 ran seeds 0..9. If the list were reordered or re-based, every
    result produced before 23 Sep 2026 would silently stop being comparable
    with everything after it, and nothing else in the suite would notice."""
    assert SEEDS[:10] == list(range(10))


def test_balanced_subsample_is_deterministic(data):
    X, y = data
    a = balanced_subsample(X, y, n_per_class=20, seed=SEED)
    b = balanced_subsample(X, y, n_per_class=20, seed=SEED)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])


def test_balanced_subsample_balances(data):
    X, y = data
    _, ys = balanced_subsample(X, y, n_per_class=20, seed=SEED)
    counts = np.bincount(ys.astype(int))
    assert counts.min() == counts.max() == 20


# --- mappings: the gap that let the bug through --------------------------------

@pytest.mark.parametrize("strategy", MAPPINGS)
def test_mapping_is_deterministic(strategy, split):
    """The regression test for the mutual_info_classif non-determinism.

    Run this before trusting any result that used a mapping.
    """
    X_tr, _, y_tr, _ = split
    a, _ = fit_mapping(X_tr, y_tr, N_QUBITS, strategy, seed=SEED)
    b, _ = fit_mapping(X_tr, y_tr, N_QUBITS, strategy, seed=SEED)
    assert np.array_equal(a, b), f"{strategy} mapping is non-deterministic"


@pytest.mark.parametrize("strategy", MAPPINGS)
def test_mapping_transform_is_deterministic(strategy, split):
    """The fitted transform must also be stable, not just the training output."""
    X_tr, X_te, y_tr, _ = split
    _, t_a = fit_mapping(X_tr, y_tr, N_QUBITS, strategy, seed=SEED)
    _, t_b = fit_mapping(X_tr, y_tr, N_QUBITS, strategy, seed=SEED)
    assert np.array_equal(t_a(X_te), t_b(X_te))


@pytest.mark.parametrize("strategy", MAPPINGS)
def test_mapping_output_shape(strategy, split):
    X_tr, X_te, y_tr, _ = split
    Xm, transform = fit_mapping(X_tr, y_tr, N_QUBITS, strategy, seed=SEED)
    assert Xm.shape == (len(X_tr), N_QUBITS)
    assert transform(X_te).shape == (len(X_te), N_QUBITS)


@pytest.mark.parametrize("strategy", ["pca", "selectk"])
def test_mapping_rejects_too_many_qubits(strategy, split):
    X_tr, _, y_tr, _ = split
    with pytest.raises(ValueError, match="exceeds feature count"):
        fit_mapping(X_tr, y_tr, X_tr.shape[1] + 1, strategy, seed=SEED)


def test_selectk_requires_labels(split):
    X_tr, _, _, _ = split
    with pytest.raises(ValueError, match="needs y_train"):
        fit_mapping(X_tr, None, N_QUBITS, "selectk", seed=SEED)


def test_unknown_mapping_raises(split):
    X_tr, _, y_tr, _ = split
    with pytest.raises(ValueError, match="Unknown mapping"):
        fit_mapping(X_tr, y_tr, N_QUBITS, "umap-ish", seed=SEED)


# --- angle scaling ------------------------------------------------------------

def test_angles_stay_in_rotation_range(split):
    """Values outside [0, pi) wrap around the Bloch sphere and make distant
    points look similar, producing a valid-looking, meaningless kernel."""
    X_tr, X_te, y_tr, _ = split
    Xm, transform = fit_mapping(X_tr, y_tr, N_QUBITS, "pca", seed=SEED)
    Xa_tr, to_angles = scale_to_angles(Xm)
    Xa_te = to_angles(transform(X_te))
    for arr in (Xa_tr, Xa_te):
        assert arr.min() >= -1e-9 and arr.max() <= np.pi + 1e-9


def test_angle_scaler_is_fit_on_train_only(split):
    """Test data must not influence the scaler; if it did, the encoded circuits
    themselves would differ, not merely a decision boundary."""
    X_tr, X_te, y_tr, _ = split
    Xm, transform = fit_mapping(X_tr, y_tr, N_QUBITS, "pca", seed=SEED)
    Xa_tr, _ = scale_to_angles(Xm)
    assert np.isclose(Xa_tr.min(), 0.0, atol=1e-9)
    assert np.isclose(Xa_tr.max(), np.pi, atol=1e-9)


def test_full_pipeline_is_deterministic(data):
    """End to end: split, map, scale. Two runs, byte-identical."""
    X, y = data

    def run():
        X_tr, X_te, y_tr, _ = make_split(X, y, seed=SEED)
        Xm, transform = fit_mapping(X_tr, y_tr, N_QUBITS, "selectk", seed=SEED)
        Xa_tr, to_angles = scale_to_angles(Xm)
        return Xa_tr, to_angles(transform(X_te))

    a_tr, a_te = run()
    b_tr, b_te = run()
    assert np.array_equal(a_tr, b_tr) and np.array_equal(a_te, b_te)
