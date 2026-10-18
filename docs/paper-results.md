# Section 4 — Results

Every figure here is the registered analysis or an explicitly exploratory family.
Nothing in this section is a follow-up analysis: §6.2a reports the one of those
there is, and it carries no verdict.

---

## 4.1 What was run

Two datasets, three training sizes, three feature mappings, five qubit counts,
four quantum settings, twenty seeds. 15,120 result records: 7,520 quantum,
7,440 classical, 160 negative-control. The geometric difference was computed
across all **360 registered units** and 7,200 per-seed rows.

Classical baselines were tuned over 396 grid points per cell against the quantum
side's 36, declared in advance as a search-size asymmetry that favours the
classical side on inner-CV scores and not on the outer test estimate, which is
what the tests use. Selection within a cell is by inner CV on training folds
only; the outer test set is touched once per (cell, seed, method).

---

## 4.2 H1: no quantum advantage on either dataset

Paired per-seed differences at the pre-registered primary cells, 250 per class,
20 seeds, intersection-union across both endpoints at alpha = 0.05.
*(`results/analysis/primary_tests.json`)*

![Figure 2 — H1's twenty paired per-seed differences at each primary cell, both datasets on one shared scale.](../results/figures/fig2_h1_paired.png)

**Figure 2** shows both datasets on one shared scale. Each figure stamps its own
source artefact into the image, so a reader can tell which run it came from
without trusting a caption.

**Churn, PCA at 12 qubits — rejects, against the quantum kernel.**

| endpoint | mean | median | 95% CI | Wilcoxon p |
| --- | --- | --- | --- | --- |
| normAP | −0.0798 | −0.0659 | [−0.1229, −0.0367] | 8.20e-05 |
| ROC-AUC | −0.0292 | −0.0171 | [−0.0457, −0.0128] | 3.38e-04 |

Both endpoints reject and both favour the classical kernel. This is not a
failure to detect an advantage; it is a detected deficit of roughly 6.6 points
of normAP at the median, in the cell chosen because it was the classical
baseline's strongest.

**The margin, stated as D6 requires.** The effect clears the *registered* MDE of
0.0171 by 4.7x and its *true* primary-cell MDE of 0.0608 by **1.31x**. The
registered figure was computed from classical-versus-classical variance and is
wrong by 3.6x on this arm. Any phrasing of the form "well clear of what the arm
was powered for" is withdrawn.

**Fraud, SelectKBest at 8 qubits — does not reject.**

| endpoint | mean | median | 95% CI | Wilcoxon p |
| --- | --- | --- | --- | --- |
| normAP | −0.0028 | −0.0014 | [−0.0072, +0.0017] | 0.245 |
| ROC-AUC | +0.0001 | +0.0005 | [−0.0017, +0.0019] | 0.823 |

Reported as a bound rather than as "no difference":

> **A true advantage larger than 0.0063 normAP at the fraud primary cell is
> excluded at 80% power.**

0.0063, not the 0.0059 section 8 registered; D6 corrects it to the primary
cell's own paired sd of 0.0095. The fraud *arm* as a whole is a different
quantity at 0.0138 and the two are never interchanged. The confirmatory script
printed the superseded 0.0059 for eleven days after D6 was written, with a
regression test pinning it; that is the fifth item in §5.6 and it is recorded
rather than quietly corrected.

---

## 4.3 The negative control is clean

The full quantum pipeline on permuted labels at each primary cell, 80 records
over 20 seeds. *(`results/analysis/negative_control_quantum.log`)*

| dataset | ROC-AUC | from 0.500 | AP vs chance | from 0 |
| --- | --- | --- | --- | --- |
| churn | 0.5058 (sd 0.0493) | +0.52 sigma | +0.0040 | +0.45 sigma |
| fraud | 0.5001 (sd 0.0452) | +0.01 sigma | −0.0008 | −0.09 sigma |

Section 7's halt condition — a consistent excess in both beyond about two
seed-level standard errors — is not met. The comparison against *chance* AP
rather than the base rate matters: the gap of +0.0154 between them is expected
and is not leakage.

---

## 4.4 H2 and H3: the prediction is not established

*(`results/audits/h2_h3_report.json`, 360 units, 7,200 per-seed rows)*

![Figure 1 — H2 across the frozen lambda sweep: rho with its 95% interval above, units retained beneath.](../results/figures/fig1_h2_lambda.png)

**Figure 1** plots this table: rho with its interval above, units retained
below, because a rho from 61 units with 299 excluded is not the same evidence as
one from all 360.

| lambda | units | excluded | breaches | rho | p | 95% CI | rho² |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1e-1 | **360** | **0** | 4/7200 | +0.1712 | 1.11e-03 | [+0.069, +0.270] | 0.0293 |
| 1e-2 | 350 | 10 | 657/7200 | −0.0245 | 0.648 | [−0.129, +0.081] | 0.0006 |
| 1e-3 | 90 | 270 | 4574/7200 | −0.3814 | 2.09e-04 | [−0.545, −0.189] | 0.1454 |
| 1e-4 | 61 | 299 | 4972/7200 | −0.2938 | 2.16e-02 | [−0.508, −0.045] | 0.0863 |
| from C † | 289 | 71 | 2893/7200 | −0.0145 | 0.806 | [−0.130, +0.101] | 0.0002 |

**† The `from C` row was computed under the λ rule D14 has since withdrawn**,
1/(2·C·n). Under the adopted 1/(2C) that column's ceiling breaches fall from
**2,893 to 979 of 7,200**, which still leaves it not breach-free. Its rho was
**not** recomputed: the verdict does not turn on it, and D14's outcome-to-verdict
mapping authorised reading the breach status and nothing further. The row stands
as the figure the published verdict was computed from, labelled, rather than
being silently replaced by a number computed after the fact.

**Both return `NOT ESTABLISHED (no breach-free lambda)`.** D5 requires the
conclusion to hold at every lambda at which no unit breaches its sqrt(n)
ceiling, and no column is breach-free.

**What that verdict is, said precisely, because three different statements are
easy to confuse here.** The registered rule returned **no verdict**. That is not
the same as the prediction having been tested and failed, and it is not the same
as finding no relationship. At lambda = 0.1 the null **is** rejected, in the
direction Huang predicts. The registered rule declined to speak because its
precondition — a column in which no unit breaches its ceiling — is met by none of
the columns.

Three things a reader needs in order to weigh that.

**It turns on four rows.** At lambda = 0.1 the column is otherwise complete —
all 360 units present, none excluded — and fails by **four breaching seeds out
of 7,200**, 0.056% of the observations, all from one cell and seed (churn,
n=100, selectk, 4 qubits, seed 7). The next-largest g/ceiling ratio anywhere is
0.9150 against those four at 1.075 to 1.093, so the dependence is discontinuous
rather than marginal. No tolerance was introduced and no seed excluded.

**The permissive reading also fails.** D5's text admits a second reading under
which the rule reduces to agreement across all five columns. That fails too,
because the sign of rho reverses: +0.17 at lambda = 0.1 against −0.38 at 1e-3
and −0.29 at 1e-4. Both readings land on the outcome D5 pre-declared for
disagreement: g's relationship to observed performance depends on the
regularisation chosen, which is a result about the metric.

**The substantive number is rho², not the verdict.** At lambda = 0.1, the only
column with a complete unselected population, **rho² = 0.0293**: the geometric
difference accounts for under three percent of the rank variance in observed
difference. A quantity explaining three percent of rank variance, whose sign
moves with a parameter the practitioner chooses, cannot tell a practitioner not
to bother. That is a claim about **usability**, not about absence, and it is the
finding the registered design called the practically valuable outcome to
establish either way.

**A third λ rule was evaluated and returned nothing to test.** Huang's own g_tra
selection over his declared grid was specified in advance (D16) and run. It does
not select a λ at all on 76.5% of the units, so it yields an incomplete column
and is reported as **unresolved** rather than as a negative result. §6.2a gives
the measurement. Counting it, three λ rules have been evaluated and none produces
a breach-free column; the third produces no column.

**H3 carries two readings and the reader picks.** Section 9 registers H3 as
subordinate to H2 and reported only if H2 is rejected. It was ungated in week 4,
for a stated and good reason, and the departure was not recorded until 29
September — after H3's result had been computed and published. A reader who
accepts the commit ordering may read H3 as confirmatory under a departure
declared late but decided early; a reader who does not should read it as
exploratory. The paper does not choose for them.

---

## 4.5 The exploratory families

Exploratory throughout, Holm-corrected within each family, and no finding here
bears on H1 or H2. Each tested level averages the cells at that level **within
each seed** before testing, because cells at one seed share a train/test split;
levels carry 20 paired observations, not pooled rows.
*(`results/analysis/exploratory_sweep.json`, `results/analysis/primary_tests.json`)*

![Figure 3 — the churn exploratory families, with Holm-significant levels in the accent colour.](../results/figures/fig3_churn_exploratory.png)

**Figure 3** shows the churn families.

**Churn.** The deficit survives correction under PCA (−0.0385, Holm 0.0189) and
SelectKBest (−0.0478, Holm 0.0060) and **not** under random projection (−0.0084,
Holm 0.3884). It survives at both tested training sizes (−0.0268 at 100,
−0.0316 at 250; the 50-per-class arm is registered as not for hypothesis
testing and is reported descriptively at −0.0315). In the qubit family only 12
survives (−0.0659, Holm 4.77e-05).

Per setting against the best classical kernel, all four lose after correction:
angle-r1 −0.0606 (Holm 0.0017), angle-r2 −0.0959 (5.34e-05), iqp-r1 −0.1011
(7.63e-06), iqp-r2 −0.3008 (7.63e-06). **The headline does not depend on the
quantum side being allowed to choose**, which is what section 9 required this
second reporting mode to show.

Across all 15 cells, two survive Holm: pca/12 at −0.0798 (Holm 0.0012) and
selectk/12 at −0.0918 (0.0082).

**Fraud.** Nothing survives anywhere. Largest magnitude +0.0045, no
Holm-adjusted p below 0.19. Three figures are **below D2's 1e-3 precision floor
and are reported as below the pipeline's resolution rather than as
measurements**: qubit 10 at −0.0008, random projection at +0.0003, training size
250 at −0.0000.

**Provenance of the per-setting and all-cells families.** Until 6 October both
were printed and never returned, so the only trace of them was three rounded
values per level in a tracked log, with no n, median, sd, confidence interval or
sensitivity t-test, and no commit, input digest or seed list. They are now
persisted with all of those. The figures above are unchanged: stdout was
byte-identical across that change on all six arms.

---

## 4.6 What these numbers do not support

Stated explicitly because each was reachable and each would have been wrong.

**No trend with qubit count.** The cell-level trend on churn is rho = −0.4692,
p = 0.0777 on n = 15 cells — not significant. Only the 12-qubit level survives
Holm. "The deficit deepens with qubit count" is not supported, and the unit of
analysis here is the cell: an earlier version of a trend statistic in this
project correlated 300 records instead of 15 cells and every figure it printed
was voided.

**No claim about fraud's ROC figures against the AP floor.** D2's floor is
1e-3 *in average precision*. Fraud's ROC-AUC mean of +0.0001 is numerically
smaller but on a different scale, and flagging it would repeat the unit
conflation D6 records.

**No claim that g carries no signal.** At lambda = 0.1 the relationship is
statistically detectable and in the predicted direction. The claim in §4.4 is
that it is not usable as a screen at that effect size with that sign
instability, which is a different and narrower statement.

**One structural reading, offered as interpretation.** On churn the deficit is
absent exactly where the classical baseline is weakest: random projection is the
mapping week 3 measured as climbing most with dimension, 0.3678 to 0.5481, and
it is the one mapping where the quantum kernel is not significantly behind. If
that holds up it inverts the usual framing, since the regime of interest is
supposed to be the one where classical methods already do well. It rests on one
dataset and one non-significant contrast.

---

## 4.7 Limitations, including two this study created

**The artefact was not available, and this conditions every limitation below
it.** The repository was **private from 17 September to 15 October 2026**, the
whole of the project's working life. It was found on 15 October, when a Software
Heritage save request failed with `visit_status: not_found` and an
unauthenticated GitHub query returned 404; the author's pushes had always
succeeded because the author is authenticated. **No reader could have checked
any claim in this study while it was being made.**

The consequence for ordering is the one that matters. D14 required its chosen
option and outcome-to-verdict mapping to be "committed and pushed before any
recomputed value is examined", and D16 was "specified in full and pushed before
it was computed". Both happened. **Neither was public.** A push to a private
remote does leave server-side receipt times the author does not set, which a
purely local commit does not, but those times are not exposed to a reader, not
verifiable by one and not citable. So every phrasing of the form *declared
publicly* or *published before the run* is **withdrawn** in favour of *committed
and pushed to a private remote before*, and the pre-commitment discipline here
is something the author practised rather than something a reader can check.

**Visibility was changed on 15 October 2026**, after two Software Heritage save
requests (2558108, 2558127) had failed with `visit_status: not_found` against the
private origin. A third request succeeded at **01:33:06 UTC on 15 October 2026**,
`visit_status: full`. A fourth was taken three minutes later. **There are two
snapshots and the reason is structural:**

    swh:1:snp:bdbf43089b1ed77f5ec9307e11f5c255dddc84dd   01:33:06, repository at 5464088
    swh:1:snp:c19a29f94639c2ea87347ae40a3d949919a75005   01:36:58, includes the commit recording the first

**A snapshot cannot contain its own citation.** The first attests the repository
as it stood when visibility changed, before any record of the archive existed; a
reader resolving it finds a §4.7 that does not mention it. The second contains
the commit that records the first, so it is the one to resolve to read this
paragraph as archived. The second is in turn cited by a commit made after it, and
**that regress does not terminate** — it is stopped here by choosing to stop, not
by completeness, and the same is true of any self-referential archive citation.

**These are the first externally verifiable facts in this study.** A third party now
attests that this repository's content existed in that exact form at or before
that instant, at a time no one here controls. Everything below describes what a
reader can do from that moment on.

**What the snapshot does not do**, stated because an archive identifier invites
being read as more than it is. It **backdates nothing**: every result, every
deviation record and every pre-commitment in this paper predates it and remains
externally unattested. It does **not** repair D11: the snapshot captures the
public refs, and `prerewrite-20260925` is not among them, so the three commit
identifiers stored in all 15,120 result records still resolve for no reader.
Archiving a repository that does not contain those commits does not make them
resolvable. What it establishes is forward-looking only: from 01:33 on 15 October
2026, a claim about this repository's state can point at something outside this
machine.

**Provenance.** Every one of the 15,120 result records stores a `git_commit`
that does not exist on the public repository. A history rewrite on 25 September
2026 changed every commit hash; the three stored hashes resolve only from a
local branch recovered from a folder that had been queued for deletion.
Annotated tags `records-0b796a3`, `records-2cf7ec7` and `records-0b2aef4` now map
those identifiers to public counterparts and carry the tree hashes in their own
messages, so the mapping arrives with a clone rather than having to be found in a
document. **That improves the delivery of the mapping and not its status**: a
reader can confirm the counterpart has the stated tree and **cannot** confirm
that the stored hash ever had it. A tag records an assertion.

Bounded precisely: a reader cannot **independently bind a historical result
record to the code that generated it**. Everything else remains checkable — the
analysis scripts in full, the data provenance and checksums, the records
themselves, and the public half of the mapping. A re-run from current HEAD
produces new evidence about the current code; it does not authenticate the old
records, since agreement is consistent with changes that do not alter these
outputs and disagreement would not separate a code change from a data or
environment change.

Full public provenance requires publishing the recovered branch
`prerewrite-20260925`, which would restore to the public repository the AI
co-authorship trailers the rewrite removed. **That decision is open and is
recorded as open.** The trade-off is stated in D11's fourth amendment and this
paper does not resolve it.

**No external timestamp, and no external reader either.** This study is not
registered at OSF and has **no Software Heritage snapshot predating its
results**. Its ordering evidence is an author-controlled history, rewritten once
on 25 September, on a remote that no one else could read until 15 October, with
no external attestation at any point. Every ordering claim in this paper,
including the claims in D13, D14 and D16 that a decision preceded a result, rests
on evidence of that class. **A reader who declines to accept it is left with
nothing**, and that is the honest statement of the position rather than a
reason to discount the claims selectively.

**No hardware.** The IBM runs registered for weeks 7 to 8 were dropped as
infeasible (D12) and no claim in this paper depends on them.

**The 50-per-class arm** resolves 0.1368, three times coarser than the 0.0427
that already disqualified it from hypothesis testing.

**One dataset is saturated.** Fraud's classical baseline sits at 0.9659 normAP
at the primary cell and is saturated at every training size tested, so one of the
two datasets could not have shown an advantage had one existed.

**The figures, and a reversed decision.** The three PNGs above are **committed**,
by name, as exceptions to the `.gitignore` rule that excludes
`results/figures/*`. An earlier draft excluded them on the ground that outputs
are regenerated rather than versioned and that
`PYTHONPATH=src python scripts/make_figures.py` reproduces them deterministically
from committed artefacts. That reasoning is sound as far as it goes and the
regeneration command still works. It was reversed for one reason it did not
address: **determinism there rests on an unpinned plotting library**, so a reader
on a different matplotlib gets a visually different figure, and a figure a paper
references but does not ship is the same defect class as a commit hash that does
not resolve. Three PNGs are 319 KB. The SVG sources remain excluded, being
regenerable and read by nothing in the paper.

**Checks this study has not completed**, listed rather than left implicit.

**The mutation harness now reads every test file, and what it reveals is worse
than what it fixed.** Until 15 October it was hardwired to one test file, so
mutants for the F20 diagnostic, the λ correction and the exploratory families
had to be run by hand. Those four are now in the suite and all 34 mutants are
killed by the test that names each one, across four source files and three test
files. But the coverage report was also scanning only the files that already had
mutants, which hid every file with none: corrected, it reads **34 of 374 test
functions**, not the 34 of 70 the old report implied. **Fifteen of eighteen test
files have no mutant at all**, including `tests/test_audit.py` and its 76
functions — the tests for the audit tool §5 is about. So the honest statement is
that this project has demonstrated non-vacuity for 9% of its test functions and
has not examined the rest.

**One check has no mutant because it has no test.** `select_lambda` in
`scripts/gtra_sweep.py`, which implements D16's selection rule, is exercised only
by that script's own control F and not by pytest, so no mutant can be expressed
for it.

**One item unchanged, and two closed since.** **Two Software Heritage snapshots
now exist**, `swh:1:snp:bdbf43089b1ed77f5ec9307e11f5c255dddc84dd` at 01:33:06
and `swh:1:snp:c19a29f94639c2ea87347ae40a3d949919a75005` at 01:36:58 UTC on
15 October 2026, after two earlier requests failed against the private origin. It postdates every result here, so it bounds the provenance gap
rather than closing it; the first paragraph of this section states what it does
and does not establish.

The other two are closed, and one of them was described wrongly here. The
`descriptive_only` rows in the exploratory output now carry the
`below_d2_floor` field the tested rows carry. The grid adequacy check was said
to have "not been extended since week 9", which misplaced the gap: the
measurement was complete and correct in week 3 and reproduces bit-identically
under current code, and what was missing was that its adjudication lived only in
prose. `scripts/check_grid_edges.py` went on printing the rule week 3 had
withdrawn, reporting UNDER-TUNED on fraud where the registered comparison
against a shuffled-label null returns adequate on both datasets. The registered
comparison is now what the script computes and what its output records; §5.6
counts the episode.
