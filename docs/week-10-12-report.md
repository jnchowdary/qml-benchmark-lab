# QML Benchmark Lab: Weeks 10 to 12 Record

Written 25 October 2026. Covers work done from 2 to 25 October 2026.

**One record for three weeks, and the reason is not tidiness.** Weeks 1 to 9
each have a record. Weeks 10 to 12 are a single registered phase, "writing",
and splitting a continuous phase into three records after the fact would invent
boundaries nobody worked to. The honest unit is the phase.

**The headline.** The registered writing was completed and the paper exists in
three generated renderings. Almost everything else in these three weeks was a
correction to this project's own records rather than new research, and the
record is materially more accurate for it. **No usable product was built, and
none was registered.** Research and writing being complete is not the same as a
tool existing, and this record says so plainly so that no later reader has to
infer it.

---

## 1. What the registered timeline asked for

Section 13 of the pre-registration assigns weeks 10 to 12 to writing. That is
done. `docs/paper.md` is 1,986 lines in nine parts, generated from eight section
files and a references file by `scripts/assemble_paper.py`, which fails if the
assembled file has drifted from its sources.

Two renderings are generated from the same markdown rather than written
separately: `docs/paper.docx` by `scripts/paper_to_docx.js`, and the arXiv
submission bundle in `arxiv/` by `scripts/paper_to_latex.py`. Neither is edited
by hand, both record their provenance, and the arXiv bundle carries the pandoc
version that built it because pandoc 2.9 and 3.12 emit materially different
output.

**Elapsed time, stated because it is the most useful number here.** Weeks 1 to
9 ran from 17 September to 2 October, sixteen days. Weeks 10 to 12 ran from
2 to 25 October, twenty-three days. The writing phase took longer than all nine
phases before it combined. Week 9's plan predicted exactly this, saying what
remained "cannot be parallelised" and that each pass surfaces a defect in the
last one.

**One earlier phase is not a report of work done, and this record says so
because the closing record is where a reader looks.** Weeks 7 and 8 were
registered as IBM hardware runs on the primary cells. They were **never feasible
as registered**: the run needs 18,172,000 circuit executions against an Open Plan
allocation of ten minutes of QPU time per month, thirty times the budget at 1 ms
per circuit and three times over at an implausible 0.1 ms. D12 records this, and
requires the word "dropped" to be replaced by that phrase wherever it appears;
§3.7 and §3.9 of the paper carried "dropped as infeasible" until this record was
written, and are corrected with it. Closing the registered study is therefore not
the same as completing every planned experiment, and the difference is two weeks
of the twelve.

---

## 2. Decisions closed in this phase

**D14 was decided and its outcome obtained.** Option (a): `lambda_from_svm_C`
becomes `1 / (2 * C)`, dropping the factor of `n`. The decision and its full
outcome-to-verdict mapping were pushed before any recomputed g was examined.
Outcome O2: 979 ceiling breaches, inside the 1,490 analytical bound published
beforehand, and the frozen columns bit-identical across six days.

**D16 was pre-committed in full, pushed, and then run.** Huang's own `g_tra`
selection rule, with the grid frozen as {1e-5, 1e-4, 1e-3, 1e-2, 0.025, 0.05,
0.1} and the threshold at 0.045. Outcome B3: the rule selects no lambda on
**76.5%** of units, 5,507 of 7,200; on 81.3% his rule and his √N ceiling cannot
both be satisfied; and every one of the 348 breaching admissible rows selected
λ ∈ {1e-5, 1e-4}.

**D17 records an error in the pre-registration and does not edit it.** The
registered text says extending a grid gains "five to seven times more on random
labels than on real ones". That is the polynomial-kernel figure: the measured
mean ratios are 5.0 and 6.6 on polynomial and 2.0 and 35.7 on RBF, so two of the
four measurements fall outside the stated range. The rule the figure supports is
unaffected, the direction holding on every kernel and both datasets. Version 1.0
stands as registered, by the rule D6 and D15 both applied.

**`prerewrite-20260925` is published.** Pushed 21 October, 25 commits, tip
`b5bf0431`. All five identifiers this study depends on are reachable from it:
`a8bafbb` and `61f7db9`, which the pre-registration cites, and `0b796a3`,
`2cf7ec7` and `0b2aef4`, which all 15,120 result records store. What decided it
was that the stated cost had already been paid: `main` already carried twenty
commits with the AI co-authorship trailers, left in place and documented on
29 September rather than rewritten.

**The OSF absence is now a decision rather than an omission.** Two weekly
records listed registration as outstanding work; D11 argued against it four days
before the first of them, on the ground that a record dated after the results
were computed would read as backdating. D11 is right and its argument is
stronger now than when it was written. Recorded as an amendment rather than left
as an unreconciled contradiction.

---

## 3. What was found about this project's own availability

**The repository was private from 17 September to 15 October**, the whole of its
working life to that point. It was found on 15 October when a Software Heritage
save request failed with `visit_status: not_found`; the author's own pushes had
always succeeded because the author is authenticated. Every phrasing of the form
*declared publicly* was withdrawn in favour of *committed and pushed to a
private remote*.

Two snapshots now exist, at 01:33:06 and 01:36:58 UTC on 15 October, the second
containing the commit that records the first, because a snapshot cannot contain
its own citation. Both predate the publication of the recovered branch by six
days, so neither archive contains it.

---

## 4. Corrections made in this phase, all of them to this project

Listed because the count matters more than the average, as week 4 put it.

1. **The registered grid adjudicator printed a verdict its own record had
   withdrawn**, for three weeks. `scripts/check_grid_edges.py` compared the gain
   from widening against the minimum detectable effect, a rule week 3 had
   already recorded as a defect, and said UNDER-TUNED on fraud where the
   registered comparison against a shuffled-label null returns adequate. The
   +0.002 threshold week 3 calls pre-declared existed nowhere in the code. The
   measurement was never wrong and reproduces bit-identically; only the
   adjudication was missing from the code.
2. **§4.7 was wrong in two of its three clauses**, having said three items were
   unchanged when one was.
3. **The week 4 error count was stated three times and no two agreed**, none of
   them right. The list runs 1 to 11; the README said twelve and the docx
   generator said ten.
4. **The mutation coverage report flattered itself**, scanning only files that
   already had mutants.
5. **D11's fourth amendment overstates its own history by half**, saying
   "roughly thirty" commits carry the AI trailers where the count is twenty.
6. **The printed exclusion bound was anchored to nothing.** `MDE_PRIMARY_CELL`
   in `primary_tests.py` and `D6_H1` in `audit_sweep.py` held the same two
   figures, one checked against regenerated records and one not, with nothing
   connecting them. They agreed; the fifth public repair was a divergence of
   exactly that kind.
7. **Three generators defaulted to not recording their output**, one of which
   published a stale document sixteen days behind its source.

§5.6 consequently went from five public repairs to seven, and its second kind
from three to four, relabelled from "claims its authors made without checking"
to "claims its authors made that their own data does not support", because the
seventh took a measurement made correctly and stated it more broadly than it
supported.

**One correction belongs to this record rather than to §5.6.** The paper's §1.2
claims to separate things published work routinely merges, and until 25 October
cited nothing for the merging. Bowles, Ahmed and Schuld measured it: of 55 arXiv
papers using the word "outperform", around 40% report a quantum model beating a
classical one and three report the reverse. It is now reference [5] and §1.2
points at the figure. The work was not consulted while this study was designed
or run. Week 4 logs a missing literature check as its largest error; this is the
same class, found seven weeks later. It does not enter §5.6's count, by the
boundary set on 5 October: an unsupported claim that turned out to be supported
misstates neither a measurement nor an instrument's behaviour.

---

## 5. What was built that the timeline did not ask for

None of this is research. All of it exists because something was found wrong.

* `scripts/assemble_paper.py` and its `--check`, so a drifted paper is a test
  failure rather than a discovery.
* `scripts/paper_to_docx.js` extended, and `scripts/check_docx_fresh.py`, which
  hashes each export's source and fails when it moves. It does not hash the
  generator and does not look inside the document; both gaps are stated in §5.6
  rather than closed.
* `scripts/paper_to_latex.py` and the `arxiv/` bundle, with two character maps,
  three refusals, and the margin fixes the Software Heritage identifiers forced.
* `scripts/adjudicate_grid.py`, which makes the registered grid decision
  checkable with `json` and `pathlib` and nothing else, where before it needed
  numpy, joblib, scikit-learn and the whole `qbench` package.
* `scripts/check_paper_figures.py`, the first thing in this repository that
  reads the paper and asks whether a figure it prints is still what the records
  say. It covers **three of 192** decimal figures and reports the rest as
  unchecked.
* `tests/test_gtra_sweep.py` and two mutants, so D16's selection rule has its
  non-vacuity demonstrated rather than assumed.

The suite stands at **487 tests** and **37 mutants, all killed, none survived**,
across five source files and four test files.

---

## 6. Verification

Everything below passes at the commit this record is added in.

* `scripts/assemble_paper.py --check`: the paper matches its nine sources.
* `scripts/check_docx_fresh.py`: three recorded exports current, none stale,
  eight provenance-unrecorded and reported as such rather than assumed.
* `scripts/check_paper_figures.py`: three figures re-derived from the stored
  records, agreeing at the precision the paper states.
* `scripts/mutation_check.py`: 37 killed, 0 survived, 0 stale.
* `pytest`: 487 passed.
* The arXiv bundle compiles under pdflatex with no errors and no missing
  packages, 33 pages, three figures embedded.

---

## 7. What is outstanding

**Nothing in the registered design.** The hypotheses are tested, the controls
are clean, the deviations are recorded, and the paper is written.

**One dependency with a person in it.** arXiv requires a personal endorsement in
quant-ph for an author with no institutional affiliation and no prior arXiv
paper, following the policy change of 21 January 2026. A request is in flight.
Until it resolves, nothing here is readable by anyone who does not already know
where to look.

**Two limitations that have no completion condition** and are stated in §4.7
with their coverage given rather than implied: mutation non-vacuity demonstrated
for 9% of test functions, 37 of 395, and the figures check covering three of the
paper's numbers.

**No product exists.** The pre-registration never promised one. The audit
protocol in §5 is a procedure with a working implementation for Tier 1 and a
partial one for Tier 2; it is not a tool anyone outside this project could pick
up today without reading the paper first. Whether to build one is a decision
this record does not make and does not pre-empt.

---

## 8. What this phase says about the project

Week 4's lesson was that a literature search is not optional, and this phase
found the same gap again seven weeks later. Week 8's lesson was that
consolidation finds things. This phase's is narrower and less comfortable: **a
green check is not evidence that the thing it checks is right.** The grid
adjudicator passed every test it had while printing a withdrawn verdict. The
mutation harness reported coverage it did not have. The first LaTeX conversion
built with zero warnings and was wrong in four places, each found by looking at
the rendered page rather than the build log. In every case the instrument
reported success and the output was wrong.

The checks added in this phase are therefore mostly checks on output rather than
on process, and the two that matter read the artefact a reader would see: the
figures check reads the paper, and the LaTeX generator refuses when markup
survives into the document. §5.6 already said a green test suite was not
evidence that a measurement tool measured anything. Three weeks of writing
produced seven more instances of it.
