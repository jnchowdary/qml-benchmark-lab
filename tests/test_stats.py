"""The rank correlation that refuses, locked down before anything depends on it.

WHY THIS FILE EXISTS
--------------------
`scipy.stats.spearmanr` returns NaN on a constant input, and every comparison
against NaN is False. So an undefined correlation silently becomes a definite
verdict, and always the reassuring one:

    nan <= 0    -> False   a "warn if not positive" branch never fires
    nan < 0.05  -> False   a "rejects" flag reads as no rejection
    nan * r > 0 -> False   an agreement check silently disagrees

This project found that in `geometric_tests.h2`, where a constant observed
difference produced NOT SUPPORTED instead of NOT ESTIMABLE, and then found seven
more unguarded calls, three of which had been emitting ConstantInputWarning on
every test run for weeks.

`qbench.stats.rank_correlation` exists so the refusal lives in one place. These
tests pin the two properties that make it worth having: `ok` is False whenever
`rho` is unusable, and `rho` is None rather than NaN so a caller who ignores
`ok` gets a TypeError instead of a wrong answer.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qbench.stats import (  # noqa: E402
    RankCorr, fmt_p, fmt_pm, fmt_rho, rank_correlation)


class TestRefusal:

    def test_constant_second_input_refuses_and_names_it(self):
        rc = rank_correlation([1, 2, 3, 4, 5], [7, 7, 7, 7, 7])
        assert rc.ok is False
        assert rc.rho is None and rc.p is None
        assert "second input is constant" in rc.why
        assert "not a null result" in rc.why

    def test_constant_first_input_refuses_and_names_it(self):
        rc = rank_correlation([3, 3, 3, 3, 3], [1, 2, 3, 4, 5])
        assert rc.ok is False
        assert "first input is constant" in rc.why

    def test_both_constant_says_both(self):
        rc = rank_correlation([1, 1, 1], [2, 2, 2])
        assert rc.ok is False
        assert "both inputs are constant" in rc.why

    def test_too_few_points_refuses(self):
        rc = rank_correlation([1, 2], [3, 4])
        assert rc.ok is False
        assert "fewer than 3" in rc.why

    def test_length_mismatch_refuses(self):
        rc = rank_correlation([1, 2, 3], [1, 2])
        assert rc.ok is False
        assert "length mismatch" in rc.why

    def test_non_finite_input_refuses(self):
        assert rank_correlation([1, 2, float("nan")], [1, 2, 3]).ok is False
        assert rank_correlation([1, 2, float("inf")], [1, 2, 3]).ok is False

    def test_min_n_is_adjustable(self):
        assert rank_correlation([1, 2, 3], [3, 2, 1], min_n=3).ok is True
        assert rank_correlation([1, 2, 3], [3, 2, 1], min_n=10).ok is False


class TestTheNumber:

    def test_a_normal_correlation_matches_scipy(self):
        from scipy import stats as sp
        x = [1, 2, 3, 4, 5, 6, 7]
        y = [2, 1, 4, 3, 6, 5, 7]
        rc = rank_correlation(x, y)
        ref = sp.spearmanr(x, y)
        assert rc.ok is True
        assert rc.rho == pytest.approx(float(ref.statistic))
        assert rc.p == pytest.approx(float(ref.pvalue))

    def test_perfect_correlation_is_plus_one(self):
        rc = rank_correlation([1, 2, 3, 4], [10, 20, 30, 40])
        assert rc.ok is True
        assert rc.rho == pytest.approx(1.0)

    def test_n_is_reported_even_on_refusal(self):
        assert rank_correlation([1, 2, 3, 4, 5], [7, 7, 7, 7, 7]).n == 5


class TestTheGuardrail:
    """The point of the type, as opposed to returning a bare (rho, p)."""

    def test_ignoring_ok_raises_rather_than_comparing_false(self):
        """This is the whole design. With NaN, `rho * 2` and `rho < 0.05` both
        succeed and produce a wrong answer. With None they raise."""
        rc = rank_correlation([1, 2, 3, 4, 5], [7, 7, 7, 7, 7])
        with pytest.raises(TypeError):
            _ = rc.rho * 2
        with pytest.raises(TypeError):
            _ = rc.rho < 0.05

    def test_truthiness_reads_as_usability(self):
        assert bool(rank_correlation([1, 2, 3], [3, 2, 1])) is True
        assert bool(rank_correlation([1, 1, 1], [3, 2, 1])) is False

    def test_a_usable_result_is_never_nan(self):
        """The invariant every caller relies on: ok implies finite."""
        rng = np.random.default_rng(0)
        for _ in range(200):
            n = int(rng.integers(2, 12))
            x = rng.integers(0, 3, size=n).astype(float)
            y = rng.integers(0, 3, size=n).astype(float)
            rc = rank_correlation(x, y)
            if rc.ok:
                assert np.isfinite(rc.rho) and np.isfinite(rc.p)
            else:
                assert rc.rho is None and rc.p is None and rc.why

    def test_scipy_warning_would_be_raised_not_printed(self):
        """If a constant input ever reaches scipy, the guards above have a hole
        and it must fail loudly rather than emit a warning nobody reads. Three
        scripts printed ConstantInputWarning on every test run for weeks."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            rank_correlation([1, 2, 3, 4], [4, 3, 2, 1])


class TestFormatting:

    def test_refusal_prints_as_na_not_as_a_number(self):
        assert fmt_rho(rank_correlation([1, 1, 1], [1, 2, 3])).strip() == "n/a"
        assert fmt_rho(rank_correlation([1, 2, 3], [3, 2, 1])).strip().startswith("-1")

    def test_underflowed_p_is_not_printed_as_zero(self):
        assert fmt_p(0.0) == "<1e-300"
        assert fmt_p(None) == "n/a"
        assert fmt_p(0.05) == "5.00e-02"

    def test_small_uncertainty_never_renders_as_zero(self):
        """The defect, with the real numbers that exposed it.

        tekeli_check.py printed `+/- 0.000` for standard errors of 3.168e-04 and
        3.099e-04 in results/audits/tekeli_churn_small.json. A reader could not
        tell those from 1e-7, or from a fit that had resolved nothing.
        """
        for v in (3.168e-04, 3.099e-04, 1e-7, 1.152e-03):
            out = fmt_pm(v)
            assert out != "0", f"{v:g} printed as a bare zero"
            assert float(out) != 0.0, f"{v:g} printed as {out!r}, which is zero"
            assert float(out) == pytest.approx(v, rel=0.05)

    def test_exact_zero_still_prints_as_zero(self):
        """An exactly-zero uncertainty is a real and different statement."""
        assert fmt_pm(0) == "0"
        assert fmt_pm(0.0) == "0"

    def test_ordinary_values_stay_readable(self):
        assert fmt_pm(0.0234) == "0.023"
        assert fmt_pm(2.0) == "2"
        assert fmt_pm(None) == "n/a"

    def test_magnitude_survives_at_any_scale(self):
        """Two standard errors three decades apart must not print the same."""
        assert fmt_pm(1e-4) != fmt_pm(1e-7)

    def test_namedtuple_fields_are_stable(self):
        """Callers unpack this; the field order is part of the contract."""
        assert RankCorr._fields == ("rho", "p", "ok", "why", "n")
