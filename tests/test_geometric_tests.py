"""H2 and H3's machinery, locked down after it produced both verdicts untested.

WHY THIS FILE EXISTS, AND WHY IT IS LATE
-----------------------------------------
`scripts/geometric_tests.py` executed two of this project's three registered
confirmatory hypotheses on 29 September 2026 and returned NOT ESTABLISHED for
both. At that moment it was 822 lines with **no tests at all**. The repository
held fifteen test files, including 73 for `audit.py` and dedicated files for
`classical_limit`, `primary_tests`, `geometric_difference` and `rbf_surrogate`.
Not one referenced this module.

Twelve defects were fixed in it that day. Every one was caught by a control with
a known answer, by an output line that looked wrong, or by the code raising on
its first real execution -- and nothing held any of the fixes in place
afterwards. Week 7 section 6 records them. This file turns each into a test that
fails against the shipped behaviour, which is how `tests/test_audit.py` reached
73 cases.

The nine controls inside the script are not a substitute and are not duplicated
here. A control proves the arithmetic is right in this run; a regression test
proves a defect that was fixed stays fixed. Both are needed and they check
different things.

WHAT IS TESTED, GROUPED BY WHAT WOULD GO WRONG WITHOUT IT
-----------------------------------------------------------
  * **Silent wrong answers.** A bare breach count with no denominator published
    "9/8" in D5. A mean over seeds would let one heavy-tailed seed carry a unit,
    which is the specific thing D7 chose the median for. An observed difference
    averaged over all twenty seeds while g is a median over the survivors pairs
    two quantities measured on different data (D8a).
  * **The strongest result reported as the weakest.** A perfect rank correlation
    gave `arctanh(1) = inf`, no interval, `ci_excludes_zero = False`, and
    therefore NOT SUPPORTED.
  * **Certainty no sample supplies.** A p-value underflowing to `0.00e+00`
    printed as if it were a result.
  * **A verdict where the data cannot support one.** H3 returning a verdict on
    eight units while H2 correctly refused; a fixed threshold that has stopped
    partitioning the data reported as a null rather than as NOT ESTIMABLE.
  * **Measuring a kernel the experiment never ran.** A hardcoded bandwidth
    instead of the record's own params, and an arm missing from the resume key
    so two arms could share one file under one label.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import geometric_tests as gt  # noqa: E402
from qbench.kernels.geometric_difference import (  # noqa: E402
    geometric_difference_regularised, normalise_kernel)

CEIL_350 = float(np.sqrt(350))      # n_per_class 250
CEIL_140 = float(np.sqrt(140))      # n_per_class 100


def row(seed, *, g=2.0, d=0.01, ceiling=CEIL_350, setting="angle-r1",
        dataset="churn", npc=250, mapping="pca", nq=12, arm="registered",
        bandwidth=1.0, **kw):
    """One per-seed sweep row, in the schema the sweep actually writes."""
    r = {"dataset": dataset, "n_per_class": npc, "mapping": mapping,
         "n_qubits": nq, "setting": setting, "seed": seed, "arm": arm,
         "quantum_params": {"embedding": setting.split("-")[0],
                            "reps": int(setting[-1]), "bandwidth": bandwidth},
         "quantum_bandwidth": bandwidth, "classical_method": "rbf",
         "classical_C": 10.0, "lambda_from_C": 1 / 3000.0, "ceiling": ceiling,
         "g": {"0.1": g, "0.01": g, "0.001": g, "0.0001": g},
         "g_from_C": g, "d_normap": d}
    r.update(kw)
    return r


def unit_rows(n_seeds=20, *, gs=None, ds=None, **kw):
    gs = gs if gs is not None else [2.0] * n_seeds
    ds = ds if ds is not None else [0.01] * n_seeds
    return [row(i, g=gs[i], d=ds[i], **kw) for i in range(n_seeds)]


def many_units(n_units, *, seeds=20, g_of=lambda i: 1.0 + i,
               d_of=lambda i: 0.01 * (i + 1), **kw):
    out = []
    for i in range(n_units):
        out += unit_rows(seeds, gs=[g_of(i)] * seeds, ds=[d_of(i)] * seeds,
                         setting=f"s{i}", nq=4 + (i % 5), **kw)
    return out


# ------------------------------------------------------------------ D7 / D8a

class TestAggregation:
    """How twenty seeds become one number, which section 6 never says."""

    def test_unit_g_is_the_median_not_the_mean(self):
        """D7 chose the median because week-4 section 9 shows one seed at 57.3.

        A mean would let that seed carry the unit. Ten seeds at 1.0 and one at
        15.0 give a median of 1.0 and a mean of 2.27, and the difference is the
        whole reason the rule exists.
        """
        gs = [1.0] * 10 + [15.0]
        u, ex, br, tot = gt.units_at(unit_rows(11, gs=gs, ceiling=18.71), "0.1")
        assert len(u) == 1
        assert u[0]["g"] == pytest.approx(1.0)
        assert u[0]["g"] != pytest.approx(float(np.mean(gs)))
        assert br == 0, "15.0 is under an 18.71 ceiling and must not be excluded"

    def test_iqr_is_reported_with_every_unit(self):
        """D7: a unit whose seeds disagree widely about g is evidence about g."""
        u, _, _, _ = gt.units_at(unit_rows(20, gs=[1.0] * 10 + [5.0] * 10), "0.1")
        assert "g_iqr" in u[0]
        assert u[0]["g_iqr"] > 0

    def test_observed_difference_uses_only_surviving_seeds(self):
        """D8(a). g is a median over survivors; d must be a mean over THE SAME
        survivors, not over all twenty.

        Here ten seeds breach and carry d = 100.0. If d averaged over all twenty
        the unit's d would be ~50; over survivors alone it is 1.0.
        """
        gs = [1.0] * 10 + [999.0] * 10
        ds = [1.0] * 10 + [100.0] * 10
        u, _, br, tot = gt.units_at(unit_rows(20, gs=gs, ds=ds), "0.1")
        assert len(u) == 1
        assert u[0]["seeds"] == 10
        assert u[0]["d"] == pytest.approx(1.0), (
            "d averaged over excluded seeds pairs a median from one seed set "
            "against a mean from another")
        assert br == 10 and tot == 20

    def test_ceiling_is_per_row_not_global(self):
        """sqrt(n_train) differs by arm: 18.71 at n=250, 11.83 at n=100.

        A g of 12.7 is under the first and over the second. Comparing every row
        against one ceiling is the error that made a hand recount contradict the
        script in week 7, where the script was right.
        """
        big = unit_rows(20, gs=[12.7] * 20, ceiling=CEIL_350, npc=250)
        small = unit_rows(20, gs=[12.7] * 20, ceiling=CEIL_140, npc=100)
        _, _, br_big, _ = gt.units_at(big, "0.1")
        u_small, ex_small, br_small, _ = gt.units_at(small, "0.1")
        assert br_big == 0
        assert br_small == 20
        assert u_small == [] and len(ex_small) == 1

    def test_unit_below_min_seeds_is_excluded_and_named(self):
        """D7: excluded, counted, and reported -- never silently dropped."""
        gs = [1.0] * (gt.MIN_SEEDS - 1) + [999.0] * 3
        u, ex, br, tot = gt.units_at(unit_rows(gt.MIN_SEEDS + 2, gs=gs), "0.1")
        assert u == []
        assert len(ex) == 1
        assert ex[0]["surviving_seeds"] == gt.MIN_SEEDS - 1
        assert ex[0]["of_seeds"] == gt.MIN_SEEDS + 2
        assert "MIN_SEEDS" in ex[0]["reason"]
        assert br == 3 and tot == gt.MIN_SEEDS + 2

    def test_breach_count_is_returned_with_its_denominator(self):
        """The defect that published "9/8" in D5, one level down.

        `classical_limit.py` printed a bare count whose real denominator was 16,
        the transcription supplied "/8" from the seed count, and an impossible
        fraction sat in a published record for four days. units_at must hand
        back the denominator so a caller cannot invent one.
        """
        out = gt.units_at(unit_rows(20, gs=[1.0] * 15 + [999.0] * 5), "0.1")
        assert len(out) == 4, "units_at must return (units, excluded, breaches, total)"
        _, _, breaches, total = out
        assert (breaches, total) == (5, 20)

    def test_from_C_column_reads_its_own_field(self):
        """lambda-from-C differs by seed, so it cannot share a key in `g`."""
        rows = unit_rows(20, gs=[2.0] * 20)
        for r in rows:
            r["g_from_C"] = 7.5
        u, _, _, _ = gt.units_at(rows, "from_C")
        assert u[0]["g"] == pytest.approx(7.5)
        u2, _, _, _ = gt.units_at(rows, "0.1")
        assert u2[0]["g"] == pytest.approx(2.0)


# ---------------------------------------------------------------------- H2

class TestH2:

    def test_perfect_correlation_is_supported_not_rejected(self):
        """rho = +1 gave arctanh(1) = inf, no interval, ci_excludes_zero False,
        and the verdict rule then called the STRONGEST possible result NOT
        SUPPORTED. rho is clamped at 1 - 1/(2n) before the z transform.
        """
        u, _, _, _ = gt.units_at(many_units(gt.MIN_UNITS + 4), "0.1")
        r = gt.h2(u)
        assert r["rho"] == pytest.approx(1.0)
        assert r["ci"][0] is not None, "a perfect correlation must still get an interval"
        assert np.isfinite(r["ci"][0]) and np.isfinite(r["ci"][1])
        assert r["ci_excludes_zero"] is True
        assert gt.verdict(r, ("rejects", "ci_excludes_zero")) == "SUPPORTED"

    def test_spearman_ci_is_finite_at_rho_one(self):
        lo, hi = gt.spearman_ci(1.0, 40)
        assert lo is not None and np.isfinite(lo) and np.isfinite(hi)
        assert lo > 0
        lo, hi = gt.spearman_ci(-1.0, 40)
        assert hi < 0

    def test_not_estimable_below_min_units(self):
        u, _, _, _ = gt.units_at(many_units(gt.MIN_UNITS - 1), "0.1")
        r = gt.h2(u)
        assert r["estimable"] is False
        assert gt.verdict(r, ("rejects", "ci_excludes_zero")) == "NOT ESTIMABLE"

    def test_above_floor_subset_is_computed(self):
        """D8(b). A rank correlation across units whose differences all sit
        below the precision floor is a correlation among noise."""
        u, _, _, _ = gt.units_at(
            many_units(gt.MIN_UNITS + 8, d_of=lambda i: 0.05 * (i + 1)), "0.1")
        r = gt.h2(u)
        assert r["n_above_floor"] == len(u)
        assert r["resolved_subset"] is not None
        assert r["resolved_subset"]["rho"] == pytest.approx(r["rho"], abs=0.2)

    def test_units_below_the_floor_are_counted_as_such(self):
        """D2's floor is what separates a measurement from arithmetic noise.

        This test was VACUOUS until the mutation check caught it, and I made it
        so. Its differences were all identical at 1e-9, which after the NaN
        guard went in makes h2 return NOT ESTIMABLE before n_above_floor is ever
        computed; `r.get("n_above_floor", 0)` then returned the default and the
        assertion held for any value of FLOOR. Loosening an assertion to make a
        test pass after a behaviour change is how a test stops testing.

        The differences now VARY while staying below the floor, so h2 runs to
        completion and the count is real.
        """
        u, _, _, _ = gt.units_at(
            many_units(gt.MIN_UNITS + 8, d_of=lambda i: 1e-9 * (i + 1)), "0.1")
        r = gt.h2(u)
        assert r["estimable"] is True, "d must vary or this tests nothing"
        assert r["n_above_floor"] == 0, f"floor is {gt.FLOOR}"
        assert r["resolved_subset"] is None, (
            "no unit clears the floor, so there is no subset to test")

    def test_constant_input_is_not_estimable(self):
        """Found by this file on its first run, as a ConstantInputWarning.

        When every unit's d is identical, Spearman is undefined and scipy
        returns NaN. Without a guard, `rejects` is bool(nan < 0.05) = False and
        the verdict reads NOT SUPPORTED -- a substantive answer -- where the
        truth is that there is no correlation to test. A verdict substituted for
        a refusal is the failure this project keeps finding.
        """
        u, _, _, _ = gt.units_at(
            many_units(gt.MIN_UNITS + 8, d_of=lambda i: 0.05), "0.1")
        r = gt.h2(u)
        assert r["estimable"] is False
        assert r["constant_d"] is True
        assert "not a null result" in r["why"]
        assert gt.verdict(r, ("rejects", "ci_excludes_zero")) == "NOT ESTIMABLE"

    def test_constant_g_is_also_not_estimable(self):
        u, _, _, _ = gt.units_at(
            many_units(gt.MIN_UNITS + 8, g_of=lambda i: 3.0), "0.1")
        r = gt.h2(u)
        assert r["estimable"] is False
        assert r["constant_g"] is True


# ---------------------------------------------------------------------- H3

class TestH3:

    def test_refuses_a_verdict_where_h2_refuses(self):
        """Eight units gave H3 NOT SUPPORTED on a 5-versus-3 comparison while
        H2 on the identical eight correctly refused. Two different answers about
        the same data is an inconsistent guard, not a finding.

        THIS TEST PREVIOUSLY PASSED FOR THE WRONG REASON, and
        `scripts/mutation_check.py` caught it on its first run. It built units
        with g = 1..8, which the g = 2 split divides 6 above and 2 below, so
        `min(above, below) < 3` refused on the degenerate partition and the
        MIN_UNITS guard was never reached. Deleting the guard the test claims to
        pin therefore changed nothing and the mutant survived.

        The fix is to balance the split so only MIN_UNITS can refuse, and to
        assert WHICH guard fired rather than only that some guard did. An
        outcome two code paths can produce is not evidence about either.
        """
        u, _, _, _ = gt.units_at(
            many_units(8, g_of=lambda i: 1.0 + 0.2 * i if i < 4 else 3.0 + i,
                       d_of=lambda i: 0.01 * (i + 1)), "0.1")
        assert len(u) == 8 < gt.MIN_UNITS
        above = [x for x in u if x["g"] > gt.G_SPLIT]
        below = [x for x in u if x["g"] <= gt.G_SPLIT]
        assert min(len(above), len(below)) >= 3, (
            "the split must be balanced, or the degenerate-partition guard "
            "fires first and this test proves nothing about MIN_UNITS")

        assert gt.h2(u)["estimable"] is False
        r3 = gt.h3(u)
        assert r3["estimable"] is False
        assert f"fewer than {gt.MIN_UNITS}" in r3["why"], (
            f"H3 must refuse for the unit count, not the partition; "
            f"it said: {r3.get('why')!r}")

    def test_degenerate_partition_is_not_estimable_not_null(self):
        """D8: at lambda 1e-2 the real run put 349 units above the split and 1
        below. A fixed threshold that has stopped partitioning the data has
        stopped being a test, which is different from p > 0.05.
        """
        u, _, _, _ = gt.units_at(
            many_units(gt.MIN_UNITS + 8, g_of=lambda i: gt.G_SPLIT + 1 + i), "0.1")
        r = gt.h3(u)
        assert r["estimable"] is False
        assert r["n_below"] == 0
        assert "stopped being a test" in r["why"]
        assert gt.verdict(r, ("rejects",)) == "NOT ESTIMABLE"

    def test_signed_secondary_is_always_reported(self):
        """D8(c). |d| cannot tell quantum winning by 0.05 from losing by 0.05,
        so the signed version is pre-declared and printed beside it."""
        u, _, _, _ = gt.units_at(
            many_units(30, g_of=lambda i: 0.5 + 0.2 * i,
                       d_of=lambda i: 0.05 if i % 2 else -0.05), "0.1")
        r = gt.h3(u)
        assert r["estimable"] is True
        assert "signed_secondary" in r
        assert {"U", "p", "median_above", "median_below"} <= set(r["signed_secondary"])

    def test_split_is_the_registered_threshold(self):
        assert gt.G_SPLIT == 2.0, "H3's threshold is registered and not retuned"

    def test_median_diff_ci_is_deterministic(self):
        """The bootstrap feeds a verdict, so it must be identical on re-run."""
        a = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
        b = [0.001, 0.002, 0.003, 0.004, 0.005, 0.006]
        assert gt._median_diff_ci(a, b, reps=500) == gt._median_diff_ci(a, b, reps=500)


# ------------------------------------------------------------------ display

class TestDisplay:

    def test_underflowed_p_is_not_printed_as_zero(self):
        """`p 0.00e+00` reads as a certainty no finite sample supplies. Same
        defect class as tekeli_check.py printing '+/- 0.000'."""
        assert gt.fmt_p(0.0) == "<1e-300"
        assert gt.fmt_p(1e-300) != "<1e-300"
        assert gt.fmt_p(0.05) == "5.00e-02"


# -------------------------------------------------------------- the fast path

class TestFastPath:

    def test_hoisted_g_equals_the_module_exactly(self):
        """The sweep hoists sqrt(K_C) and the per-lambda solve out of the
        setting loop for a 4x saving. That is worth nothing if it moves a digit.
        """
        rng = np.random.default_rng(0)
        X = rng.normal(size=(40, 5))
        sq = np.sum((X[:, None, :] - X[None, :, :]) ** 2, axis=-1)
        # NOT exp(-gamma * sq): that has a unit diagonal, normalise_kernel is
        # the identity on it, and the test was then blind to the normalisation
        # being dropped entirely. The mutation check caught that. A linear
        # kernel has a varying diagonal, so normalisation does real work here.
        K_c = np.exp(-0.3 * sq)
        K_q = X @ X.T + 5.0 * np.eye(40)
        assert not np.allclose(np.diag(K_q), 1.0), (
            "K_q must have a non-unit diagonal or normalisation is a no-op")
        lams = (1e-1, 1e-3)
        fast, ceiling = gt.g_for_settings(K_c, {"q": K_q}, lams)
        for lam in lams:
            ref = geometric_difference_regularised(K_c, K_q, lam=lam)
            assert fast["q"][lam] == pytest.approx(ref, abs=1e-12)
        assert ceiling == pytest.approx(float(np.sqrt(40)))

    def test_identical_kernels_give_mu_over_mu_plus_lambda_not_one(self):
        """g(K, K) is NOT 1. The control that first asserted 1 failed by
        1.24e-02, and the expectation was wrong rather than the code.

        This matters beyond the control: "g near 1 rules advantage out" has a
        lambda-dependent floor strictly below 1, so comparing g to 1 at large
        lambda is biased toward finding no advantage.
        """
        rng = np.random.default_rng(1)
        X = rng.normal(size=(30, 4))
        sq = np.sum((X[:, None, :] - X[None, :, :]) ** 2, axis=-1)
        K = np.exp(-0.4 * sq)
        mu = float(np.linalg.eigvalsh(normalise_kernel(K)).max())
        out, _ = gt.g_for_settings(K, {"same": K}, (1e-1, 1e-8))
        assert out["same"][1e-1] == pytest.approx(mu / (mu + 1e-1), abs=1e-9)
        assert out["same"][1e-1] < 1.0
        assert out["same"][1e-8] == pytest.approx(1.0, abs=1e-6)


# ------------------------------------------------------------------- the sweep

class TestSweepPlumbing:

    def test_load_takes_a_path_not_a_string(self):
        """sweep() raised AttributeError on the first line of its first real run
        after three commits described this analysis as fixed in advance of its
        data. primary_tests.load takes a Path; audit.load takes a str.
        """
        import primary_tests
        assert primary_tests.load(Path("/definitely/not/here.jsonl")) is None
        with pytest.raises(AttributeError):
            primary_tests.load("/definitely/not/here.jsonl")

    def test_check_inputs_fails_on_a_missing_file(self, tmp_path):
        """The nine controls all exercise arithmetic and none opens a file,
        which is exactly why the str/Path error survived."""
        assert gt.check_inputs(["churn"], [250], str(tmp_path), str(tmp_path),
                               "registered") is False

    def test_sweep_refuses_to_mix_arms_in_one_file(self, tmp_path):
        """Without the arm in the resume key, a resumed run against the other
        arm finds the (dataset, size, cell, seed) key present and skips
        silently, leaving a file that looks complete and holds two arms' g under
        one label.
        """
        out = tmp_path / "g.jsonl"
        out.write_text(json.dumps(row(0, arm="registered")) + "\n")
        with pytest.raises(SystemExit) as e:
            gt.sweep(["churn"], [250], str(out), str(tmp_path), str(tmp_path),
                     arm="bandwidth")
        assert "one arm per file" in str(e.value).lower()

    def test_cli_accepts_test_and_units(self):
        """--test and --units were in the docstring's usage block and never in
        argparse, so --test failed with an unrecognised argument.

        This test survived two mutations before it worked. Scraping --help and
        asserting `"--test" in text` stayed true when the flag was renamed to
        --test-GONE, because one is a substring of the other. Adding a word
        boundary did not help either: the help string for --units reads "sweep
        output to test (with --test)", so the assertion was satisfied by prose
        in a different argument's help text.

        It now reads the parser's actual option strings. A flag that exists and
        a flag that is merely mentioned are different things, and only an exact
        set membership distinguishes them.
        """
        opts = {o for action in gt.build_parser()._actions
                for o in action.option_strings}
        for flag in ("--test", "--units", "--arm", "--qubits", "--mappings",
                     "--controls-only", "--report", "--limit"):
            assert flag in opts, (
                f"{flag} is not an option string on the parser; "
                f"it has {sorted(opts)}")

    def test_lambda_columns_are_the_frozen_sweep_plus_from_C(self):
        """D5 freezes (1e-1, 1e-2, 1e-3, 1e-4) plus lambda-from-C."""
        assert gt.LAMBDAS == (1e-1, 1e-2, 1e-3, 1e-4)
        assert gt.LAM_COLS == ("0.1", "0.01", "0.001", "0.0001", "from_C")

    def test_registered_universe_is_360_units(self):
        """2 datasets x 3 mappings x 5 qubit counts x 3 sizes x 4 settings."""
        assert (len(gt.MAPPINGS) * len(gt.QUBITS) * len(gt.SIZES)
                * len(gt.SETTINGS) * 2) == gt.REGISTERED_UNITS == 360


# ------------------------------------------------------- the negative control

class TestNegativeControl:

    def test_no_signal_is_not_supported_on_both(self):
        """A stage that finds a result in noise is worse than one that finds
        nothing. This is control H, kept as a test because a control proves
        today's arithmetic and a test proves the behaviour stays.
        """
        rng = np.random.default_rng(11)
        rows = []
        for i in range(60):
            base = 1.0 + 4.0 * rng.random()
            rows += unit_rows(20, gs=[base + rng.normal(0, 0.15) for _ in range(20)],
                              ds=[float(rng.normal(0, 0.003)) for _ in range(20)],
                              setting=f"s{i}", nq=4 + i % 5)
        u, _, _, _ = gt.units_at(rows, "0.1")
        assert gt.verdict(gt.h2(u), ("rejects", "ci_excludes_zero")) == "NOT SUPPORTED"
        assert gt.verdict(gt.h3(u),
                          ("rejects", "ci_excludes_zero", "exceeds_floor")) \
            == "NOT SUPPORTED"

    def test_all_nine_script_controls_pass(self):
        """The script refuses to report H2 or H3 if one fails, so the controls
        are load-bearing and a control silently removed stops protecting
        anything.

        This called only `test_controls()` -- the five on the aggregation and
        the tests -- while its name claimed nine. Controls A, B, C and I live in
        `controls()`, which it never invoked, so mutating control B's
        expectation back to the wrong g(K,K) = 1 left it passing. Both are
        called now.
        """
        assert gt.controls(verbose=False) is True, "A, B, C, I"
        assert gt.test_controls(verbose=False) is True, "D, E, F, G, H"
