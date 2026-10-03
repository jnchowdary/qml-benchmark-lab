# Paper draft

**Status, 3 October 2026.** DRAFT. The results section below is written and every
figure is cited to the artefact it comes from. The framing is **not decided** and
is not decided here; section 1 sets out the fork and what each branch costs.
Nothing in section 3 changes between the two branches, which is why it could be
written first.

---

## 1. The one decision that blocks everything else

Section 8 of the pre-registration describes a kernel-comparison paper and
commits that *"the paper is written the same way in each case"*. Since week 4
this project's centre of gravity has moved to an audit protocol, with churn and
fraud as the worked example. **No deviation record declares that**, and
`docs/audit-protocol.md` is referenced throughout `deviations.md` only
incidentally.

**Branch A — the registered paper.** A pre-registered comparison of quantum
kernel SVMs against tuned classical kernel SVMs on imbalanced business tabular
data, leading with section 8's registered lead: *"g not validated. H2 not
rejected. Given 360 units, this would be a meaningfully powered negative result
about a metric the field currently takes on trust, and the paper leads with
it."* The audit protocol appears as a methods contribution.

**Branch B — the audit-protocol paper.** The protocol is the contribution; the
churn and fraud comparison is the worked example that produced it, and the
deviations record is evidence that the checks catch real defects.

**What it costs to choose B.** A departure from section 8 that section 11
requires be recorded with its date and whether it was decided before or after
the results were seen. D13 is the precedent and the warning: H3 was ungated in
week 4 for a good reason, the reason was never written into `deviations.md`, and
when it was finally declared on 29 September the lateness cost it a confirmatory
reading. **Declaring the framing before the writing costs one short record;
declaring it after a referee notices costs the same credibility D13 lost.**

**What it costs to choose A.** The strongest thing this project has produced is
arguably the protocol and the record of what it caught, and A subordinates that
to a null result.

This section is replaced by the decision once taken, and the deviation record
carries the reasoning.

---

## 2. Outline

Sections 3 to 5 are common to both branches. Only the ordering and the framing
of 2 and 6 differ.

1. **Introduction.** The claim under test and why business tabular data is the
   right place to test it.
2. **Background.** Huang's geometric difference as a pre-training screen; what
   the field takes on trust. (Branch B: the audit problem instead.)
3. **Design.** Pre-registration, primary cells, endpoints, decision rule, power.
   Section 3 of this draft is the results that design produced.
4. **Results.** Written below.
5. **The protocol.** The checks, each tied to a defect it caught here.
   (Branch A: methods. Branch B: the contribution.)
6. **Discussion and limitations.** Including provenance, below.
7. **Deviations.** A pointer to `deviations.md`, not a summary of it.

---

## 3. Results

### 3.1 What was run

Two datasets, three training sizes, three feature mappings, five qubit counts,
four quantum settings, twenty seeds. 15,120 result records: 7,520 quantum,
7,440 classical, 160 negative-control. The geometric difference was computed
across all **360 registered units** and 7,200 per-seed rows.

Classical baselines were tuned over 396 grid points per cell against the quantum
side's 36, declared in advance as a search-size asymmetry that favours the
classical side on inner-CV scores and not on the outer test estimate, which is
what the tests use. Selection within a cell is by inner CV on training folds
only; the outer test set is touched once per (cell, seed, method).

### 3.2 H1: no quantum advantage on either dataset

Paired per-seed differences at the pre-registered primary cells, 250 per class,
20 seeds, intersection-union across both endpoints at alpha = 0.05.
*(`results/analysis/primary_tests.json`)*

**Figure 2** shows both datasets on one shared scale.

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
quantity at 0.0138 and the two are never interchanged.

### 3.3 The negative control is clean

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

### 3.4 H2 and H3: the geometric difference is not validated

*(`results/audits/h2_h3_report.json`, 360 units, 7,200 per-seed rows)*

**Figure 1** plots this table: rho with its interval above, units retained
below, because a rho from 61 units with 299 excluded is not the same evidence as
one from all 360.

| lambda | units | excluded | breaches | rho | p | 95% CI | rho² |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1e-1 | **360** | **0** | 4/7200 | +0.1712 | 1.11e-03 | [+0.069, +0.270] | 0.0293 |
| 1e-2 | 350 | 10 | 657/7200 | −0.0245 | 0.648 | [−0.129, +0.081] | 0.0006 |
| 1e-3 | 90 | 270 | 4574/7200 | −0.3814 | 2.09e-04 | [−0.545, −0.189] | 0.1454 |
| 1e-4 | 61 | 299 | 4972/7200 | −0.2938 | 2.16e-02 | [−0.508, −0.045] | 0.0863 |
| from C | 289 | 71 | 2893/7200 | −0.0145 | 0.806 | [−0.130, +0.101] | 0.0002 |

**Both return `NOT ESTABLISHED (no breach-free lambda)`.** D5 requires the
conclusion to hold at every lambda at which no unit breaches its sqrt(n)
ceiling, and no column is breach-free.

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
difference. As a pre-training screen on this data that is close to worthless
taken at face value, and it is the finding the registered design called the
practically valuable outcome to establish either way.

**H3 carries two readings and the reader picks.** Section 9 registers H3 as
subordinate to H2 and reported only if H2 is rejected. It was ungated in week 4,
for a stated and good reason, and the departure was not recorded until 29
September — after H3's result had been computed and published. A reader who
accepts the commit ordering may read H3 as confirmatory under a departure
declared late but decided early; a reader who does not should read it as
exploratory. The paper does not choose for them.

### 3.5 The exploratory families

Exploratory throughout, Holm-corrected within each family, and no finding here
bears on H1 or H2. Each tested level averages the cells at that level **within
each seed** before testing, because cells at one seed share a train/test split;
levels carry 20 paired observations, not pooled rows.
*(`results/analysis/exploratory_sweep.json`, `results/analysis/primary_tests.log`)*

**Figure 3** shows the churn families. **Churn.** The deficit survives correction under PCA (−0.0385, Holm 0.0189) and
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

### 3.6 What these numbers do not support

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

**One structural reading, offered as interpretation.** On churn the deficit is
absent exactly where the classical baseline is weakest: random projection is the
mapping week 3 measured as climbing most with dimension, 0.3678 to 0.5481, and
it is the one mapping where the quantum kernel is not significantly behind. If
that holds up it inverts the usual framing, since the regime of interest is
supposed to be the one where classical methods already do well. It rests on one
dataset and one non-significant contrast.

---

## 4. Limitations, including two this project created

**Provenance.** Every one of the 15,120 result records stores a `git_commit`
that does not exist on the public repository. A history rewrite on 25 September
2026 changed every commit hash; the three stored hashes resolve only from a
local branch recovered from a folder that had been queued for deletion. A
tree-identity mapping to public counterparts exists and is recorded, but a reader
can verify that the counterpart has the stated tree and **cannot** verify that
the stored hash ever had it. Full public provenance requires publishing that
branch, which would restore the AI co-authorship trailers the rewrite removed.
The paper states which choice was made.

**No external timestamp.** This project is not registered at OSF, has no
Software Heritage snapshot predating its results, and its ordering evidence is
an author-controlled history that has already been rewritten once.

**No hardware.** The IBM runs registered for weeks 7 to 8 were dropped as
infeasible and no claim in this paper depends on them.

**The 50-per-class arm** resolves 0.1368, three times coarser than the 0.0427
that already disqualified it from hypothesis testing.

---

## 5. Figures

| file | shows |
| --- | --- |
| `results/figures/fig1_h2_lambda.{png,svg}` | H2 across the sweep: rho with 95% CI, and units retained beneath it |
| `results/figures/fig2_h1_paired.{png,svg}` | H1's twenty paired seeds at each primary cell, one shared scale |
| `results/figures/fig3_churn_exploratory.{png,svg}` | the churn exploratory families, Holm-significant levels in the accent |

**These files are not in the repository.** `.gitignore` line 7 excludes
`results/figures/*`, consistent with `results/runs` and `results/kernels`:
outputs are regenerated, not versioned. Run
`PYTHONPATH=src python scripts/make_figures.py` to produce them from the
committed artefacts. Regeneration is deterministic — figure 2's jitter is
seeded at 0 and the other two draw nothing random — so a reader gets the same
figures the paper describes.

Each figure stamps its own source artefact into the image. The palette was
validated before use rather than chosen by eye, and the layout was checked by
rendering and looking at the output, which caught a label collision in figures
2 and 3 and a near-clipped interval in figure 1.

---

## 6. What this draft does not yet contain

* **Sections 1, 2, 5, 6, 7 of the outline.** Only the results, figures and
  limitations are drafted.
* **Two tables are stdout only.** The 15-cell sweep and the per-setting
  comparison exist in `results/analysis/primary_tests.log` and nowhere
  structured; the figures quoted in 3.5 were read from that log.
* **The lambda-from-C column** is computed under a rule D14 records as
  unsourced and probably wrong by a factor of n. It appears in the table in 3.4
  and is not load-bearing for any statement in this draft.
