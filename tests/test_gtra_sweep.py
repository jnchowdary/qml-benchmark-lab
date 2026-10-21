"""Tests for D16's selection rule, which until now had none.

WHY THIS FILE EXISTS
--------------------
§4.7 of the paper says, of the mutation harness:

    One check has no mutant because it has no test. `select_lambda` in
    `scripts/gtra_sweep.py`, which implements D16's selection rule, is exercised
    only by that script's own control F and not by pytest, so no mutant can be
    expressed for it.

Control F is a good check and runs before every sweep, but it runs inside the
script. A defect reintroduced into `select_lambda` would be caught only by
someone running the sweep again, and the sweep takes hours. The mutation harness
maps each mutant to a pytest node id, so a rule with no pytest test cannot have
its non-vacuity demonstrated at all. These tests exist so that two mutants can.

WHAT THEY ADD OVER CONTROL F
----------------------------
Control F tests four dictionaries, all of them monotone in lambda. The rule is
specified over the admissible SET, deliberately, so that a monotonicity
violation surfaces as a selection the gate can catch rather than as a silently
wrong answer. `test_selection_does_not_assume_monotonicity` is the case control
F does not cover: an admissible set with a hole in it, where an implementation
that scanned for the first violation would return the wrong lambda while
agreeing with control F on every monotone input.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import gtra_sweep as gs  # noqa: E402


class TestSelectLambda:
    """D16 sections 1 and 5: the largest grid lambda with g_tra <= 0.045."""

    def test_the_grid_and_threshold_are_the_ones_D16_froze(self):
        """Both were committed and pushed before any result was computed, which
        is the only thing that makes the rule a pre-commitment rather than a
        choice. A test that re-derived them from the data would defeat that."""
        assert gs.HUANG_GRID == (1e-5, 1e-4, 1e-3, 1e-2, 0.025, 0.05, 0.1)
        assert gs.GTRA_MAX == 0.045
        assert gs.NEAR_BOUNDARY == 1e-9

    def test_selection_takes_the_largest_admissible_lambda(self):
        """Largest, not smallest, and not the first one found.

        The direction is the whole rule. Huang's g_tra is non-decreasing in
        lambda, so taking the smallest admissible value would select 1e-5 almost
        everywhere and the rule would say nothing about the data.
        """
        mixed = {l: (0.001 if l <= 1e-2 else 0.9) for l in gs.HUANG_GRID}
        selected, admissible, _ = gs.select_lambda(mixed)
        assert selected == 1e-2
        assert admissible is True

    def test_no_admissible_lambda_returns_none_rather_than_a_fallback(self):
        """On 76.5% of the units this is what happens, so it is the common path
        and not the edge case. Returning a fallback lambda here would have
        turned 'the rule selects nothing' into a verdict, which is the finding
        D16 was run to obtain."""
        hard = {l: 0.9 for l in gs.HUANG_GRID}
        selected, admissible, near = gs.select_lambda(hard)
        assert selected is None
        assert admissible is False
        assert near == 0

    def test_the_threshold_is_inclusive(self):
        """D16 fixed `<=` where the source is internally inconsistent between
        `<=` and `<`. A lambda sitting exactly on 0.045 is admissible, and the
        near-boundary counter records that the other reading would have moved
        it, so the two readings can be told apart afterwards rather than argued
        about."""
        at_bound = {l: (0.001 if l < 1e-2 else 0.9) for l in gs.HUANG_GRID}
        at_bound[1e-2] = gs.GTRA_MAX
        selected, admissible, near = gs.select_lambda(at_bound)
        assert selected == 1e-2
        assert admissible is True
        assert near == 1

    def test_selection_does_not_assume_monotonicity(self):
        """The case control F does not cover.

        g_tra is non-decreasing in lambda, so the admissible set should be a
        down-set and this input should never occur. The rule is nevertheless
        specified over the set rather than over the first violation, so that a
        monotonicity failure shows up as a selection the gate can catch. Here
        1e-5 and 0.1 are admissible and everything between them is not: taking
        the maximum of the admissible set gives 0.1, while scanning upward for
        the first violation gives 1e-5. An implementation that agreed with
        control F on every monotone input could still differ here.
        """
        holed = {l: 0.9 for l in gs.HUANG_GRID}
        holed[1e-5] = 0.001
        holed[0.1] = 0.001
        selected, admissible, _ = gs.select_lambda(holed)
        assert selected == 0.1, "the maximum is over the admissible set, not up to the first gap"
        assert admissible is True

    def test_near_boundary_counts_every_lambda_at_the_threshold(self):
        """Not just the selected one. The count exists to say how much of the
        sweep would move under the other reading of the threshold, so it has to
        cover rows the selection never looks at."""
        two_at_bound = {l: 0.9 for l in gs.HUANG_GRID}
        two_at_bound[1e-3] = gs.GTRA_MAX
        two_at_bound[0.05] = gs.GTRA_MAX
        selected, admissible, near = gs.select_lambda(two_at_bound)
        assert near == 2
        assert selected == 0.05

    @pytest.mark.parametrize("value,admitted", [
        (0.045 - 1e-12, True),
        (0.045, True),
        (0.045 + 1e-12, False),
    ])
    def test_the_boundary_is_where_the_rule_says_it_is(self, value, admitted):
        d = {l: 0.9 for l in gs.HUANG_GRID}
        d[1e-3] = value
        selected, _, _ = gs.select_lambda(d)
        assert (selected == 1e-3) is admitted
