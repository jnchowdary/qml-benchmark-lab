"""The LaTeX generator's break-opportunity pass, exercised rather than described.

WHY THIS FILE EXISTS
--------------------
`scripts/paper_to_latex.py` builds the arXiv submission and had no test. Every
defect ever found in it was found by rendering a page and looking: an accented
`o` printing as `Fl'{o}rez`, a minus sign printing literal dollar signs, an
empty radical, 46 dollar signs leaking into verbatim.

On 26 October 2026 it produced one more, and that one is the argument for this
file. Three paths ran past the right margin, the worst by 43.2pt, and the third
was not cosmetic: `blastchar/telco-customer-churn` overflowed its column in the
3.1 table and collided with `mlg-ulb/creditcardfraud` beside it. The repair
inserts `\\allowbreak` after a path separator. Its first draft also matched the
slash inside pandoc's italic correction `\\/`, which pandoc emits between the
hyphens of `--flag` to stop the ligature, so `--check` gained a break
opportunity in the middle of itself.

**Then the fix for THAT was written with doubled backslashes**, so the shipped
lookbehind meant "not preceded by two backslashes" and would have let the bug
straight back in. It survived because the check written for it was a throwaway
script holding the correct pattern while the file on disk held the wrong one.
A test that imports the module cannot make that mistake.

WHAT IS ASSERTED, AND WHAT DELIBERATELY IS NOT
----------------------------------------------
Observable behaviour only. Nothing here asserts a regex spelling, a particular
lookbehind, or the order of the substitutions: an implementation that reaches
the same output by another route must pass, and one that reaches the wrong
output by the expected route must fail. The strongest assertion is the
round-trip invariant, which is spelling-independent by construction: deleting
every `\\allowbreak{}` from the output must give back the input exactly, so the
pass can add break opportunities and can do nothing else.
"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from paper_to_latex import add_break_opportunities, SEQSPLIT_MIN  # noqa: E402

BREAK = "\\allowbreak{}"


def strip_breaks(s):
    return s.replace(BREAK, "")


class TestNothingButBreakOpportunitiesIsAdded:
    """The invariant that makes every other test safe."""

    @pytest.mark.parametrize("span", [
        r"\texttt{scripts/foreign/kakavand\_adapter.py}",
        r"\texttt{scripts/check\_paper\_figures.py}",
        r"\texttt{blastchar/telco-customer-churn}",
        r"\texttt{mlg-ulb/creditcardfraud}",
        r"\texttt{-\/-check}",
        r"\texttt{n\_qubits}",
        r"\texttt{lightning.qubit}",
        r"\texttt{K\_train\_quantum}",
    ])
    def test_deleting_the_breaks_restores_the_input(self, span):
        out, _, _ = add_break_opportunities(span)
        assert strip_breaks(out) == span

    def test_it_holds_over_a_whole_document(self):
        doc = ("Prose with \\texttt{docs/audit-protocol.md} and a flag "
               "\\texttt{-\\/-hook-sample}, plus \\texttt{results/analysis/"
               "grid\\_edges\\_*\\_both*.json} and some \\verb|untouched| text.\n"
               "A second line with \\texttt{scripts/tekeli\\_check.py}.\n")
        out, _, _ = add_break_opportunities(doc)
        assert strip_breaks(out) == doc


class TestPathsBecomeBreakable:
    """The three spans that ran past the margin, and why they did."""

    @pytest.mark.parametrize("path,separators", [
        ("scripts/foreign/kakavand\\_adapter.py", 3),   # two slashes, one underscore
        ("scripts/check\\_paper\\_figures.py", 3),      # one slash, two underscores
        ("blastchar/telco-customer-churn", 1),          # the 3.1 table collision
        ("mlg-ulb/creditcardfraud", 1),
    ])
    def test_one_break_opportunity_per_separator(self, path, separators):
        out, _, permitted = add_break_opportunities("\\texttt{" + path + "}")
        assert out.count(BREAK) == separators
        assert permitted == [path]

    def test_a_break_follows_its_separator_rather_than_preceding_it(self):
        """A line ending in `scripts/` is readable; one ending in `scripts`
        with the slash orphaned onto the next line is not."""
        out, _, _ = add_break_opportunities(r"\texttt{a/b}")
        assert out == "\\texttt{a/" + BREAK + "b}"

    def test_a_span_with_no_separator_is_untouched(self):
        for span in (r"\texttt{lightning.qubit}", r"\texttt{NOT ESTABLISHED}"):
            out, _, permitted = add_break_opportunities(span)
            assert out == span and permitted == []


class TestPandocsItalicCorrectionSurvivesIntact:
    """`--flag` reaches LaTeX as `-\\/-flag`. A break between those hyphens
    would split `--check` across a line as `-` and `-check`, which is the
    first defect this repair introduced and the second one it nearly shipped.
    """

    @pytest.mark.parametrize("flag", ["-\\/-check", "-\\/-hook-sample",
                                      "-\\/-out", "-\\/-cell-fields"])
    def test_the_command_is_returned_byte_for_byte(self, flag):
        span = "\\texttt{" + flag + "}"
        out, _, permitted = add_break_opportunities(span)
        assert out == span, "a break was inserted into an italic correction"
        assert permitted == []

    def test_no_break_ever_lands_immediately_after_a_backslash_slash(self):
        """Stated as the observable outcome rather than as a pattern: whatever
        the implementation, `\\/` must never be followed by a break."""
        doc = ("\\texttt{-\\/-check} \\texttt{-\\/-hook-sample} "
               "\\texttt{scripts/a.py} \\texttt{docs/b.md}")
        out, _, _ = add_break_opportunities(doc)
        assert "\\/" + BREAK not in out
        assert out.count(BREAK) == 2, "the two real paths should still break"

    def test_a_flag_and_a_path_in_one_span_break_only_at_the_path(self):
        out, _, _ = add_break_opportunities(r"\texttt{-\/-hook scripts/x.py}")
        assert "\\/" + BREAK not in out
        assert out.count(BREAK) == 1


class TestTheSeqsplitPathIsUnchanged:
    """The long-identifier rule predates this repair and must still fire."""

    def test_a_long_span_with_no_control_sequence_is_seqsplit(self):
        ident = "a" * (SEQSPLIT_MIN + 5)
        out, split, permitted = add_break_opportunities("\\texttt{" + ident + "}")
        assert out == "\\texttt{\\seqsplit{" + ident + "}}"
        assert split == [ident] and permitted == []

    def test_a_long_span_containing_a_control_sequence_is_not_seqsplit(self):
        """Why the exclusion exists: seqsplit walks its argument token by
        token, and a global redefinition over spans containing `\\_` produced
        12 LaTeX errors."""
        ident = "a" * SEQSPLIT_MIN + "\\_b"
        out, split, _ = add_break_opportunities("\\texttt{" + ident + "}")
        assert "\\seqsplit" not in out and split == []

    def test_a_short_span_is_not_seqsplit_even_with_separators(self):
        out, split, _ = add_break_opportunities(r"\texttt{a/b}")
        assert split == [] and "\\seqsplit" not in out


class TestTheCountsReported:
    """Both numbers reach docs/latex-manifest.json, so they have to mean
    something. An earlier version of this script reported every candidate as
    split, including the ones it declined."""

    def test_declined_spans_are_not_counted(self):
        doc = (r"\texttt{-\/-check} \texttt{lightning.qubit} "
               r"\texttt{scripts/a.py} \texttt{" + "b" * (SEQSPLIT_MIN + 1) + "}")
        _, split, permitted = add_break_opportunities(doc)
        assert len(split) == 1
        assert len(permitted) == 1
        assert permitted == ["scripts/a.py"]
