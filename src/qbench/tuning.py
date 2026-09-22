"""Nested cross-validated tuning for kernel SVMs, on precomputed Gram matrices.

Design
------
Outer loop = the 10 seeds in qbench.data.SEEDS: each seed is one stratified
train/test split. Inner loop = stratified k-fold CV on the outer-train portion
only, used to choose hyperparameters. The outer test set is touched exactly
once, after selection, which is what makes the reported score an unbiased
estimate.

Every kernel, classical now and quantum from week 4, goes through the same
path: SVC(kernel="precomputed"). Identical folds, identical solver, identical
selection rule; only the Gram matrix differs. That is what licenses the paired
statistical tests in week 9.

Gram slicing
------------
The kernels here are pointwise: k(x, x') depends only on x and x'. So the Gram
matrix over the outer-train set is computed ONCE per structural setting and
each inner fold's train and validation blocks are sliced out of it. This is
identical to recomputing per fold (tested), and for quantum kernels it cuts
circuit evaluations by roughly a factor of n_splits.

Known, accepted bias
--------------------
Feature mapping and angle scaling are fit on the outer-train set, so inside
the inner CV the validation fold has influenced the mapping. For unsupervised
steps (PCA, random projection, min-max scaling) this is standard practice. For
SelectKBest it is a mild optimistic bias in INNER scores only. The outer test
estimate, which is the number reported, is unaffected: the outer test fold
never influences anything before it is scored.

Why the grids are wide
----------------------
Under-tuning the classical baseline is the most common way this literature
manufactures an apparent quantum advantage. `edge_flags` reports any selected
hyperparameter sitting on the boundary of its grid, which means the optimum
may lie outside the searched range and the baseline may be under-tuned.
Explicit grids are used instead of sklearn's data-dependent gamma='scale' so
that every searched value is written down and reproducible.
"""

from __future__ import annotations

import time
import warnings
from dataclasses import asdict, dataclass

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.svm import SVC

__all__ = [
    "C_GRID",
    "CLASSICAL_GRIDS",
    "MAX_ITER",
    "matched_grids",
    "unconstrained_grids",
    "Selection",
    "select_hyperparameters",
    "edge_flags",
    "evaluate",
    "tune_and_evaluate",
]

# 0.001 to 10,000, one value per decade. Widened on 21 Sep 2026 after the first
# smoke run: linear hit the old minimum (0.01) and poly the old maximum (1000).
# Widening was driven by inner-CV edge flags only; no test score was consulted.
C_GRID = tuple(float(10.0**k) for k in range(-4, 5))

# Hard cap on SVC solver iterations. Without it, an ill-conditioned kernel can
# run indefinitely: poly degree 4 at gamma=1 on 4 angle features reached kernel
# values of 4.2e5 and failed to converge after 2e6 iterations (measured 21 Sep
# 2026). A fit that hits the cap is treated as FAILED, never scored.
MAX_ITER = 1_000_000

# RBF on angle features in [0, pi]: squared distances reach about 10*d, so an
# absolute gamma grid from 1e-3 to 1e2 in half-decades spans nearly constant
# to nearly diagonal kernels at every qubit count from 2 to 8.
RBF_ANGLE_GRID = [{"gamma": float(g)} for g in np.round(10.0 ** np.arange(-3.0, 2.01, 0.5), 10)]


# Poly widened on 21 Sep 2026: in the first smoke run 11 of 18 poly fits chose
# the old top multiplier (3) and 10 of 18 the old top degree (4). The top
# corner (degree 5, m=10) is ill-conditioned and often fails to converge; the
# convergence guard excludes those points rather than the grid omitting them,
# so the search is as wide as the solver can honestly support.
POLY_DEGREES = (2, 3, 4, 5)
POLY_MULTIPLIERS = (0.1, 1.0, 3.0, 10.0)


def matched_grids(d):
    """Grids for the matched track: d angle features in [0, pi].

    Poly gamma is scale-relative, gamma = m / (d * pi^2), so gamma * x.x' <= m
    whatever the qubit count. An absolute poly gamma is not safe: the same
    value that is benign at d=2 is ill-conditioned at d=8. With m in
    {0.1, 1, 3}, every fit converged in <= 0.1 s with max|K| <= 139 across
    d in {2, 4, 8} (measured). m=10 and degree 5 were added after edge flags;
    some of those points do not converge and are excluded by the guard.
    """
    return {
        "linear": [{}],
        "rbf": RBF_ANGLE_GRID,
        "poly": [
            {"degree": deg, "gamma": float(m / (d * np.pi**2)), "coef0": c0}
            for deg in POLY_DEGREES
            for m in POLY_MULTIPLIERS
            for c0 in (0.0, 1.0)
        ],
    }


def unconstrained_grids(d):
    """Grids for the unconstrained track: d standardised features.

    Standardised dot products scale with d, so both RBF and poly gamma are
    expressed relative to 1/d (the idea behind sklearn's gamma='scale'), with
    every searched value written down.
    """
    return {
        "linear": [{}],
        "rbf": [{"gamma": float(m / d)} for m in np.round(10.0 ** np.arange(-2.0, 2.01, 0.5), 10)],
        "poly": [
            {"degree": deg, "gamma": float(m / d), "coef0": c0}
            for deg in POLY_DEGREES
            for m in POLY_MULTIPLIERS
            for c0 in (0.0, 1.0)
        ],
    }


# Kept for the tests and for quick use at d=4.
CLASSICAL_GRIDS = matched_grids(4)


@dataclass
class Selection:
    params: dict
    C: float
    inner_score: float
    grid_scores: list
    edge: list
    n_fits: int
    n_nonconverged: int
    seconds: float


def _fit(K_tr, y_tr, C, max_iter):
    """Fit, returning (model, converged)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        model = SVC(kernel="precomputed", C=C, class_weight="balanced", max_iter=max_iter).fit(K_tr, y_tr)
    converged = not any(issubclass(w.category, ConvergenceWarning) for w in caught)
    return model, converged


def _fit_score(K_tr, y_tr, K_val, y_val, C, max_iter):
    """PR-AUC on the validation fold, or None if the solver did not converge."""
    model, converged = _fit(K_tr, y_tr, C, max_iter)
    if not converged:
        return None
    return float(average_precision_score(y_val, model.decision_function(K_val)))


def select_hyperparameters(gram_fn, param_grid, X_tr, y_tr, *, seed, c_grid=C_GRID, n_splits=5, max_iter=MAX_ITER):
    """Inner-CV grid search over structural parameters x C.

    gram_fn(params) must return a callable k(X, Y=None) -> Gram matrix.
    Scoring is PR-AUC (average precision), matching the primary metric.

    Ties are broken deterministically: highest score, then the smaller C (the
    more regularised model), then earliest position in the grid.

    A grid point where ANY fold fails to converge is excluded from selection
    (score recorded as None) and counted in n_nonconverged. A half-fitted
    model must never be ranked alongside converged ones.
    """
    t0 = time.perf_counter()
    X_tr, y_tr = np.asarray(X_tr, dtype=float), np.asarray(y_tr)
    folds = list(StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed).split(X_tr, y_tr))

    rows, n_fits, n_bad = [], 0, 0
    for order, params in enumerate(param_grid):
        K = np.asarray(gram_fn(params)(X_tr), dtype=float)  # once per structural setting
        for C in c_grid:
            scores, failed = [], False
            for tr, va in folds:
                sc = _fit_score(K[np.ix_(tr, tr)], y_tr[tr], K[np.ix_(va, tr)], y_tr[va], C, max_iter)
                n_fits += 1
                if sc is None:
                    n_bad += 1
                    failed = True
                    break  # this grid point is excluded; skip its remaining folds
                scores.append(sc)
            rows.append({"params": dict(params), "C": float(C),
                         "score": None if failed else float(np.mean(scores)), "order": order})

    valid = [r for r in rows if r["score"] is not None]
    if not valid:
        raise RuntimeError("No grid point converged in every fold; the grid is unusable for this data.")
    best = sorted(valid, key=lambda r: (-round(r["score"], 12), r["C"], r["order"]))[0]
    return Selection(
        params=best["params"],
        C=best["C"],
        inner_score=best["score"],
        grid_scores=[{k: v for k, v in r.items() if k != "order"} for r in rows],
        edge=edge_flags(best["params"], best["C"], param_grid, c_grid, grid_scores=rows),
        n_fits=n_fits,
        n_nonconverged=n_bad,
        seconds=time.perf_counter() - t0,
    )


def _score_lookup(grid_scores):
    import json as _json
    return {(_json.dumps(g["params"], sort_keys=True), g["C"]): g["score"] for g in grid_scores}


def _is_plateau(lookup, params, C, alt_params, alt_C, tol=1e-12):
    """True if the neighbouring grid point scored identically (a flat region)."""
    import json as _json
    a = lookup.get((_json.dumps(params, sort_keys=True), C))
    b = lookup.get((_json.dumps(alt_params, sort_keys=True), alt_C))
    return a is not None and b is not None and abs(a - b) <= tol


def edge_flags(best_params, best_C, param_grid, c_grid=C_GRID, grid_scores=None):
    """Hyperparameters whose selected value sits at the edge of the searched range.

    Only parameters with at least 3 distinct searched values are checked: a
    parameter searched over 2 values is always 'at an edge', so flagging it
    would be noise.

    Plateau-aware when grid_scores is given: an edge choice is NOT flagged if
    its neighbouring grid value scored identically. Found 22 Sep 2026: linear
    SVM ranking, and therefore PR-AUC, is invariant to C once C is small enough
    that every dual variable sits at its bound. The tie-break then picks the
    smallest C, which lands on the grid edge. In 49 of 49 such linear fits the
    score at C=1e-4 equalled the score at C=1e-3 exactly. Extending the grid
    could never change anything there, so flagging it was a false alarm.
    """
    lookup = _score_lookup(grid_scores) if grid_scores is not None else None
    flags = []
    cs = sorted(set(c_grid))
    if len(cs) >= 3:
        for edge_C, nbr_C, label in ((cs[0], cs[1], "grid minimum"), (cs[-1], cs[-2], "grid maximum")):
            if best_C == edge_C:
                if lookup is None or not _is_plateau(lookup, best_params, best_C, best_params, nbr_C):
                    flags.append(f"C={best_C:g} ({label})")
    for key in sorted({k for p in param_grid for k in p}):
        vals = sorted({p[key] for p in param_grid if key in p})
        if len(vals) < 3 or key not in best_params:
            continue
        v = best_params[key]
        for edge_v, nbr_v, label in ((vals[0], vals[1], "grid minimum"), (vals[-1], vals[-2], "grid maximum")):
            if v == edge_v:
                nbr = dict(best_params, **{key: nbr_v})
                if lookup is None or not _is_plateau(lookup, best_params, best_C, nbr, best_C):
                    flags.append(f"{key}={v:g} ({label})")
    return flags


def evaluate(kernel, X_tr, y_tr, X_te, y_te, C, max_iter=MAX_ITER):
    """Fit once on the full outer-train set, score once on the outer test set."""
    t0 = time.perf_counter()
    K_tr = np.asarray(kernel(X_tr), dtype=float)
    K_te = np.asarray(kernel(X_te, X_tr), dtype=float)
    model, converged = _fit(K_tr, y_tr, C, max_iter)
    fit_s = time.perf_counter() - t0
    scores = model.decision_function(K_te)
    return {
        "test_average_precision": float(average_precision_score(y_te, scores)),
        "test_roc_auc": float(roc_auc_score(y_te, scores)),
        "test_f1": float(f1_score(y_te, model.predict(K_te), zero_division=0)),
        "test_base_rate": float(np.mean(y_te)),
        "n_support": int(model.n_support_.sum()),
        "final_converged": converged,
        "fit_seconds": fit_s,
    }


def _ranked(grid_scores):
    """Converged grid points, best first, with the same tie-break as selection."""
    valid = [(i, r) for i, r in enumerate(grid_scores) if r["score"] is not None]
    return [r for _, r in sorted(valid, key=lambda ir: (-round(ir[1]["score"], 12), ir[1]["C"], ir[0]))]


MAX_FALLBACKS = 5


def tune_and_evaluate(name, gram_fn, param_grid, X_tr, y_tr, X_te, y_te, *, seed, c_grid=C_GRID, n_splits=5, max_iter=MAX_ITER):
    """Full nested procedure for one method on one outer split.

    If the selected setting's FINAL fit on the whole outer-train set fails to
    converge (it needs more iterations than any single fold did), fall back to
    the next-best converged setting, up to MAX_FALLBACKS times. The rank used
    is recorded in `final_fallback_rank` (0 = the selected setting). A
    non-converged final model's test score is never reported as if it were
    trustworthy: if every fallback fails, `final_converged` is False.

    `C` is kept at top level because week 6 needs it: lambda_from_svm_C(C, n)
    sets the regularisation of the geometric difference from the classical
    model actually being compared against.
    """
    sel = select_hyperparameters(gram_fn, param_grid, X_tr, y_tr, seed=seed, c_grid=c_grid, n_splits=n_splits, max_iter=max_iter)
    ranked = _ranked(sel.grid_scores)
    chosen, out, rank = ranked[0], None, 0
    for rank, cand in enumerate(ranked[: MAX_FALLBACKS + 1]):
        out = evaluate(gram_fn(cand["params"]), X_tr, y_tr, X_te, y_te, cand["C"], max_iter=max_iter)
        chosen = cand
        if out["final_converged"]:
            break

    record = {"method": name, "seed": seed, "n_train": int(len(y_tr)), "n_test": int(len(y_te))}
    record.update({k: v for k, v in asdict(sel).items() if k != "grid_scores"})
    record.update(params=chosen["params"], C=chosen["C"], inner_score=chosen["score"],
                  final_fallback_rank=rank,
                  edge=edge_flags(chosen["params"], chosen["C"], param_grid, c_grid,
                                  grid_scores=sel.grid_scores))
    record.update(out)
    record["grid_scores"] = sel.grid_scores
    return record
