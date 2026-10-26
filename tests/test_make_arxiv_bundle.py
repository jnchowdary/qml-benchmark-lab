"""What goes into the arXiv submission, derived rather than declared.

WHY THIS FILE EXISTS
--------------------
The bundle directory holds ten files and the submission needs four. Archiving
the directory is the obvious move and it is wrong: it sweeps in `paper.pdf`
beside its own source, which arXiv handles badly, plus `header.tex`, the
intermediate markdown and three build artefacts.

The first plan was to write the four filenames in README.md. That plan was
refuted by this project's own week: a true sentence in that file went stale
within a day, because nothing executes a document. So the list is read out of
`paper.tex` and these tests hold that derivation to its behaviour -- add a
figure to the document and the bundle gains it, with nothing to remember.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from make_arxiv_bundle import required_files, MAIN  # noqa: E402

DOC = "\\documentclass{article}\n\\begin{document}\n%s\n\\end{document}\n"


class TestTheListComesOutOfTheDocument:

    def test_a_figure_added_to_the_tex_is_added_to_the_bundle(self):
        """The whole point. Nothing has to be remembered or updated."""
        one, _ = required_files(DOC % r"\includegraphics{a.png}")
        two, _ = required_files(DOC % r"\includegraphics{a.png}\includegraphics{b.png}")
        assert one == [MAIN, "a.png"]
        assert two == [MAIN, "a.png", "b.png"]

    def test_the_main_file_comes_first(self):
        """arXiv picks the main file by looking for \\documentclass; putting it
        first makes the archive listing legible to a person checking."""
        got, _ = required_files(DOC % r"\includegraphics{z.png}")
        assert got[0] == MAIN

    def test_a_figure_used_twice_is_included_once(self):
        got, _ = required_files(DOC % r"\includegraphics{a.png} and \includegraphics{a.png}")
        assert got == [MAIN, "a.png"]

    def test_graphics_options_do_not_confuse_it(self):
        got, _ = required_files(DOC % r"\includegraphics[width=0.8\textwidth]{a.png}")
        assert got == [MAIN, "a.png"]

    def test_an_input_is_carried_too(self):
        """A \\input IS referenced, unlike header.tex which pandoc inlines."""
        got, _ = required_files(DOC % r"\input{table.tex}")
        assert got == [MAIN, "table.tex"]

    def test_a_document_with_no_figures_is_just_the_tex(self):
        got, problems = required_files(DOC % "plain prose")
        assert got == [MAIN] and problems == []


class TestItRefusesRatherThanShippingSomethingWrong:

    def test_a_directory_component_is_refused(self):
        """arXiv unpacks at the root. A path with a directory would create a
        subdirectory with nothing at the top level."""
        _, problems = required_files(DOC % r"\includegraphics{figures/a.png}")
        assert problems and "flat archive" in problems[0]

    def test_a_parent_reference_is_refused(self):
        _, problems = required_files(DOC % r"\includegraphics{../a.png}")
        assert problems

    def test_a_file_with_no_documentclass_is_not_a_main_file(self):
        _, problems = required_files("\\usepackage{fvextra}\n")
        assert any("documentclass" in p for p in problems)


class TestAgainstTheRealBundle:
    """The four that go and the six that must not, on the actual submission."""

    @pytest.fixture
    def tex(self):
        p = ROOT / "arxiv" / MAIN
        if not p.exists():
            pytest.skip("arxiv/paper.tex not built; run scripts/paper_to_latex.py")
        return p.read_text(encoding="utf-8")

    def test_exactly_the_tex_and_its_figures(self, tex):
        got, problems = required_files(tex)
        assert problems == []
        assert got[0] == MAIN
        assert sorted(got[1:]) == ["fig1_h2_lambda.png", "fig2_h1_paired.png",
                                   "fig3_churn_exploratory.png"]

    def test_header_tex_is_not_included(self, tex):
        """Pandoc's -H inlines it into the preamble, so the document never
        references it, and a second .tex invites arXiv to pick the wrong main
        file."""
        got, _ = required_files(tex)
        assert "header.tex" not in got

    def test_the_compiled_pdf_is_not_included(self, tex):
        """The one that matters: arXiv wants source, and a PDF sitting beside
        it is not ignored."""
        got, _ = required_files(tex)
        assert not any(f.endswith(".pdf") for f in got)

    def test_build_artefacts_and_the_intermediate_markdown_are_not_included(self, tex):
        got, _ = required_files(tex)
        for f in ("paper.aux", "paper.log", "paper.toc", "paper_source.md"):
            assert f not in got

    def test_what_the_bundle_directory_holds_is_not_what_is_submitted(self, tex):
        """States the trap as an assertion: the directory and the submission
        are different sets, so archiving the directory is wrong."""
        got, _ = required_files(tex)
        present = {p.name for p in (ROOT / "arxiv").iterdir() if p.is_file()}
        assert set(got) < present, "if these were equal the script would be pointless"

    def test_the_figures_agree_with_what_the_generator_recorded(self, tex):
        import json
        m = ROOT / "docs" / "latex-manifest.json"
        if not m.exists():
            pytest.skip("no manifest")
        got, _ = required_files(tex)
        recorded = json.loads(m.read_text(encoding="utf-8")).get("figures", [])
        assert sorted(got[1:]) == sorted(recorded)
