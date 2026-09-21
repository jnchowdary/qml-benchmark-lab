"""Tests for the nested-CV tuning engine.

The engine is shared by every kernel in the project, so a flaw here would
contaminate every comparison. These tests pin: the Gram-slicing shortcut is
exact, selection is deterministic, the outer test set cannot influence
selection, and under-tuned grids are flagged.
"""

import warnings

import numpy as np
import pytest

from qbench.data import balanced_subsample, load_dataset, make_split
from qbench.features import fit_mapping, scale_to_angles
from qbench.kernels.classical import build_classical_kernel
from qbench.tuning import (
    C_GRID,
    CLASSICAL_GRIDS,
    edge_flags,
    evaluate,
    matched_grids,
    select_hyperparameters,
    tune_and_evaluate,
    unconstrained_grids,
)

SMALL_C = (0.1, 1.0, 10.0)


@pytest.fixture(scope="module")
def prepared():
    X, y, _ = load_dataset("synthetic")
    X, y = balanced_subsample(X, y, n_per_class=40, seed=0)
    X_tr, X_te, y_tr, y_te = make_split(X, y, seed=0)
    Xm, transform = fit_mapping(X_tr, y_tr, 4, "pca", seed=0)
    Xa, to_angles = scale_to_angles(Xm)
    return Xa, to_angles(transform(X_te)), y_tr, y_te


def gram(name):
    return lambda p: build_classical_kernel(name, **p)


# --- the Gram-slicing shortcut ------------------------------------------------

@pytest.mark.parametrize("name,params", [("rbf", {"gamma": 0.5}), ("poly", {"degree": 3, "gamma": 0.1, "coef0": 1.0}), ("linear", {})])
def test_gram_slicing_equals_direct_computation(prepared, name, params):
    """Slicing fold blocks out of one Gram matrix must equal computing them
    directly. If this ever fails, the shortcut is invalid for that kernel."""
    X = prepared[0]
    k = build_classical_kernel(name, **params)
    K = k(X)
    a, b = np.arange(0, 20), np.arange(20, 40)
    assert np.allclose(K[np.ix_(b, a)], k(X[b], X[a]))
    assert np.allclose(K[np.ix_(a, a)], k(X[a]))


# --- selection ------------------------------------------------------------------

def test_selection_is_deterministic(prepared):
    X, _, y, _ = prepared
    grid = CLASSICAL_GRIDS["rbf"][:5]
    a = select_hyperparameters(gram("rbf"), grid, X, y, seed=0, c_grid=SMALL_C)
    b = select_hyperparameters(gram("rbf"), grid, X, y, seed=0, c_grid=SMALL_C)
    assert (a.params, a.C, a.inner_score) == (b.params, b.C, b.inner_score)


def test_selection_searches_every_combination(prepared):
    X, _, y, _ = prepared
    grid = CLASSICAL_GRIDS["rbf"][:3]
    sel = select_hyperparameters(gram("rbf"), grid, X, y, seed=0, c_grid=SMALL_C, n_splits=5)
    assert len(sel.grid_scores) == len(grid) * len(SMALL_C)
    assert sel.n_fits == len(grid) * len(SMALL_C) * 5


def test_selected_combination_has_the_best_score(prepared):
    X, _, y, _ = prepared
    sel = select_hyperparameters(gram("rbf"), CLASSICAL_GRIDS["rbf"][:5], X, y, seed=0, c_grid=SMALL_C)
    assert sel.inner_score == pytest.approx(max(r["score"] for r in sel.grid_scores if r["score"] is not None))


def test_ties_resolve_to_smallest_C_and_first_grid_entry():
    """Identical inputs make every setting score the same. The rule must then
    pick the most regularised model deterministically, not whichever came last."""
    rng = np.random.default_rng(0)
    X = np.zeros((40, 3))
    y = rng.permutation([0] * 20 + [1] * 20)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sel = select_hyperparameters(gram("rbf"), CLASSICAL_GRIDS["rbf"][:3], X, y, seed=0, c_grid=SMALL_C)
    assert sel.C == min(SMALL_C)
    assert sel.params == CLASSICAL_GRIDS["rbf"][0]


# --- leakage ----------------------------------------------------------------------

def test_outer_test_labels_cannot_influence_selection(prepared):
    """Shuffling the outer test labels must change the test metrics but leave
    the chosen hyperparameters untouched."""
    X_tr, X_te, y_tr, y_te = prepared
    grid = CLASSICAL_GRIDS["rbf"][:5]
    a = tune_and_evaluate("rbf", gram("rbf"), grid, X_tr, y_tr, X_te, y_te, seed=0, c_grid=SMALL_C)
    y_shuffled = np.random.default_rng(1).permutation(y_te)
    b = tune_and_evaluate("rbf", gram("rbf"), grid, X_tr, y_tr, X_te, y_shuffled, seed=0, c_grid=SMALL_C)
    assert (a["params"], a["C"], a["inner_score"]) == (b["params"], b["C"], b["inner_score"])


# --- edge flags: the under-tuning alarm ---------------------------------------

def test_edge_flag_raised_for_C_at_maximum():
    flags = edge_flags({}, max(C_GRID), [{}], C_GRID)
    assert any("C=" in f and "maximum" in f for f in flags)


def test_edge_flag_raised_for_gamma_at_minimum():
    grid = CLASSICAL_GRIDS["rbf"]
    flags = edge_flags(grid[0], 1.0, grid, C_GRID)
    assert any("gamma" in f and "minimum" in f for f in flags)


def test_no_edge_flag_for_interior_choice():
    grid = CLASSICAL_GRIDS["rbf"]
    assert edge_flags(grid[len(grid) // 2], 1.0, grid, C_GRID) == []


def test_two_valued_parameter_is_never_flagged():
    """coef0 is searched over {0, 1}: always 'at an edge', so flagging it is noise."""
    grid = CLASSICAL_GRIDS["poly"]
    best = grid[len(grid) // 2]
    assert not any("coef0" in f for f in edge_flags(best, 1.0, grid, C_GRID))


# --- outer evaluation -----------------------------------------------------------

def test_evaluate_metrics_are_valid(prepared):
    X_tr, X_te, y_tr, y_te = prepared
    out = evaluate(build_classical_kernel("rbf", gamma=0.5), X_tr, y_tr, X_te, y_te, C=1.0)
    for k in ("test_average_precision", "test_roc_auc", "test_f1"):
        assert 0.0 <= out[k] <= 1.0
    assert out["test_base_rate"] == pytest.approx(float(np.mean(y_te)))


def test_tuned_rbf_beats_chance_on_learnable_data(prepared):
    X_tr, X_te, y_tr, y_te = prepared
    rec = tune_and_evaluate("rbf", gram("rbf"), CLASSICAL_GRIDS["rbf"], X_tr, y_tr, X_te, y_te, seed=0)
    assert rec["test_average_precision"] > rec["test_base_rate"] + 0.1


def test_record_carries_what_week_6_needs(prepared):
    """C must be recorded: lambda_from_svm_C(C, n) derives the geometric
    difference's regularisation from it."""
    X_tr, X_te, y_tr, y_te = prepared
    rec = tune_and_evaluate("linear", gram("linear"), CLASSICAL_GRIDS["linear"], X_tr, y_tr, X_te, y_te, seed=0)
    for key in ("method", "seed", "params", "C", "inner_score", "edge", "n_train",
                "test_average_precision", "test_base_rate", "grid_scores",
                "n_nonconverged", "final_converged", "final_fallback_rank"):
        assert key in rec


# --- the grids themselves ---------------------------------------------------------

def test_grids_are_as_wide_as_documented():
    gammas = [p["gamma"] for p in CLASSICAL_GRIDS["rbf"]]
    assert min(gammas) == pytest.approx(1e-3) and max(gammas) == pytest.approx(1e2)
    assert len(gammas) == 11
    assert min(C_GRID) == pytest.approx(1e-4) and max(C_GRID) == pytest.approx(1e4)


# --- solver convergence: the hang found on 21 Sep 2026 -------------------------

ILL_CONDITIONED = {"degree": 4, "gamma": 1.0, "coef0": 1.0}  # max|K| ~4e5 on 4 angle features


def test_nonconverging_grid_point_is_excluded_not_scored(prepared):
    """A half-fitted model must never be ranked alongside converged ones."""
    X, _, y, _ = prepared
    grid = [ILL_CONDITIONED, {"degree": 2, "gamma": 0.01, "coef0": 1.0}]
    sel = select_hyperparameters(gram("poly"), grid, X, y, seed=0, c_grid=(1.0, 100.0), max_iter=2_000)
    assert sel.n_nonconverged > 0
    assert sel.params == grid[1]
    failed = [r for r in sel.grid_scores if r["params"] == ILL_CONDITIONED]
    assert failed and all(r["score"] is None for r in failed)


def test_grid_with_no_converging_point_raises(prepared):
    X, _, y, _ = prepared
    with pytest.raises(RuntimeError, match="No grid point converged"):
        select_hyperparameters(gram("poly"), [ILL_CONDITIONED], X, y, seed=0, c_grid=(100.0,), max_iter=500)


def test_final_model_convergence_is_recorded(prepared):
    X_tr, X_te, y_tr, y_te = prepared
    out = evaluate(build_classical_kernel("rbf", gamma=0.5), X_tr, y_tr, X_te, y_te, C=1.0)
    assert out["final_converged"] is True


@pytest.mark.parametrize("d", [2, 4, 8])
def test_matched_poly_gamma_is_scale_relative(d):
    """gamma * max(x.x') = gamma * d * pi^2 must equal the multiplier m, whatever d."""
    ms = sorted({round(p["gamma"] * d * np.pi**2, 9) for p in matched_grids(d)["poly"]})
    assert ms == [0.1, 1.0, 3.0, 10.0]


@pytest.mark.parametrize("d", [2, 8])
def test_worst_case_matched_poly_converges(d):
    """Largest multiplier, highest degree, largest C: the configuration most
    likely to be ill-conditioned must still converge under the default cap."""
    rng = np.random.default_rng(0)
    X = rng.uniform(0, np.pi, size=(200, d))
    y = (X.sum(axis=1) > X.sum(axis=1).mean()).astype(int)
    # the pre-widening worst case (degree 4, m=3, C=1000) must still converge;
    # the new top corner (degree 5, m=10) is allowed to fail and is excluded
    g = 3.0 / (d * np.pi**2)
    out = evaluate(build_classical_kernel("poly", degree=4, gamma=g, coef0=1.0), X, y, X, y, C=1000.0)
    assert out["final_converged"]


def test_unconstrained_gamma_scales_with_dimension():
    g10 = sorted(p["gamma"] for p in unconstrained_grids(10)["rbf"])
    g30 = sorted(p["gamma"] for p in unconstrained_grids(30)["rbf"])
    assert np.allclose(np.array(g10) * 10, np.array(g30) * 30)


def test_final_fit_failure_falls_back_to_next_best(prepared, monkeypatch):
    """If the selected setting converges in every fold but its final fit on the
    full training set does not, the next-best converged setting is used and
    the fallback is recorded."""
    import qbench.tuning as tuning

    real_evaluate = tuning.evaluate
    calls = {"n": 0}

    def flaky_evaluate(*args, **kwargs):
        out = real_evaluate(*args, **kwargs)
        calls["n"] += 1
        if calls["n"] == 1:
            out["final_converged"] = False
        return out

    monkeypatch.setattr(tuning, "evaluate", flaky_evaluate)
    X_tr, X_te, y_tr, y_te = prepared
    rec = tuning.tune_and_evaluate("rbf", gram("rbf"), CLASSICAL_GRIDS["rbf"][:5], X_tr, y_tr, X_te, y_te,
                                   seed=0, c_grid=SMALL_C)
    assert rec["final_fallback_rank"] == 1
    assert rec["final_converged"] is True


def test_no_fallback_needed_in_normal_case(prepared):
    X_tr, X_te, y_tr, y_te = prepared
    rec = tune_and_evaluate("rbf", gram("rbf"), CLASSICAL_GRIDS["rbf"][:5], X_tr, y_tr, X_te, y_te, seed=0, c_grid=SMALL_C)
    assert rec["final_fallback_rank"] == 0
