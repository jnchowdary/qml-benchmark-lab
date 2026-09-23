"""Chance-level average precision.

WHY THIS FILE EXISTS
--------------------
On 23 Sep 2026 the negative control appeared to show a 2.2-sigma leak on churn
and 2.5-sigma on fraud. It was not a leak. The claim built into the verdict
block -- that a random ranker's average precision equals the base rate -- is
false at finite sample size, and I had asserted it from intuition rather than
deriving or checking it. That is the same failure that produced the plateau
misreading and the fraud base-rate error: a number I was confident about,
never tested.

So these tests do not check that qbench.metrics agrees with me. They check it
against an analytic special case and against sklearn's own scorer under
simulation, which are independent of whatever I believed.
"""

import numpy as np
import pytest
from sklearn.metrics import average_precision_score

from qbench.metrics import (
    ap_chance_for_record,
    chance_average_precision,
    normalised_average_precision,
)


def test_single_positive_matches_the_analytic_value():
    """With one positive at a uniformly random rank R, AP = 1/R exactly, so
    E[AP] = H_n / n. Closed form, no simulation, no opinion."""
    for n in (5, 20, 100, 500):
        harmonic = sum(1.0 / r for r in range(1, n + 1))
        assert chance_average_precision(n, 1) == pytest.approx(harmonic / n, rel=1e-12)


@pytest.mark.parametrize("n,p", [(30, 15), (60, 30), (150, 75), (200, 40)])
def test_exact_value_matches_sklearn_under_simulation(n, p):
    """The formula must agree with the scorer the pipeline actually uses.

    A derivation that is right about some other definition of average
    precision would be worse than useless here.
    """
    rng = np.random.default_rng(0)
    y = np.zeros(n, dtype=int)
    y[:p] = 1
    trials = 4000
    aps = [average_precision_score(y, rng.normal(size=n)) for _ in range(trials)]
    mc_mean = float(np.mean(aps))
    mc_se = float(np.std(aps, ddof=1)) / np.sqrt(trials)
    assert chance_average_precision(n, p) == pytest.approx(mc_mean, abs=4 * mc_se)


@pytest.mark.parametrize("n,p", [(30, 15), (150, 75), (448, 148), (600, 300)])
def test_chance_is_strictly_above_the_base_rate(n, p):
    """The whole point. If this ever equalled the base rate, the negative
    control would be reading against the wrong null again."""
    assert chance_average_precision(n, p) > p / n


def test_bias_shrinks_as_the_test_set_grows():
    """Small test sets have a higher chance floor, which is why the
    training-size sweep cannot be compared on raw AP."""
    bias = [chance_average_precision(n, n // 2) - 0.5 for n in (30, 60, 150, 600)]
    assert bias == sorted(bias, reverse=True)
    assert bias[0] > 0.04 and bias[-1] < 0.01


def test_the_learning_curve_correction_is_material():
    """Concrete: churn pca/12 linear scored 0.7527 at 50 per class and 0.8192
    at 250. The raw gap of 0.0665 understates the real one, because the small
    arm sits on a floor 0.036 higher."""
    small = normalised_average_precision(0.7527, 30, 15)
    large = normalised_average_precision(0.8192, 150, 75)
    raw_gap = 0.8192 - 0.7527
    assert (large - small) > raw_gap + 0.02


def test_normalisation_puts_chance_at_zero_and_perfect_at_one():
    for n, p in ((150, 75), (448, 148)):
        assert normalised_average_precision(chance_average_precision(n, p), n, p) == pytest.approx(0.0, abs=1e-12)
        assert normalised_average_precision(1.0, n, p) == pytest.approx(1.0, abs=1e-12)


def test_record_helper_recovers_the_positive_count():
    rec = {"n_test": 150, "test_base_rate": 0.5}
    assert ap_chance_for_record(rec) == chance_average_precision(150, 75)


def test_degenerate_inputs_raise_rather_than_return_nonsense():
    with pytest.raises(ValueError):
        chance_average_precision(10, 0)
    with pytest.raises(ValueError):
        chance_average_precision(0, 0)
    assert chance_average_precision(10, 10) == 1.0
