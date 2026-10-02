# Week 9 — statistics and the exploratory sweep

**Registered scope**, section 13: *"Week 9: statistics and the exploratory
sweep."*

**Status.** The exploratory sweep is complete on both datasets. Section 8's
result statements are written below with the figures D6 corrected, not the ones
section 8 registered. The confirmatory verdicts are unchanged: H1 rejects on
churn against the quantum kernel, H1 does not reject on fraud, H2 and H3 return
NOT ESTABLISHED. No number in this report is new evidence about any of them.

---

## 1. What was already done, and what week 9 added

No quantum compute was required. The raw records were complete before week 9
began: 15 cells x 20 seeds x 4 settings at every training size, both datasets,
7,200 quantum and 5,400 classical records.

Section 9 names five exploratory families. Two were already computed and
Holm-corrected inside `scripts/primary_tests.py` and are in
`results/analysis/primary_tests.log`, printed but never persisted as structured
output: the 15-cell sweep (`report_sweep`) and the per-setting comparison
(`report_per_setting`). The other four had no output in any form.

Week 9 added `scripts/exploratory_sweep.py` and
`results/analysis/exploratory_sweep.json`, covering the qubit-count trend,
per-mapping breakdowns, the training-size comparison and the learning curve.

---

## 2. Section 8's result statements, with D6's figures

### Churn: no quantum advantage, and a measured classical advantage

H1 rejects at the pre-registered primary cell, PCA at 12 qubits, 250 per class,
20 paired seeds, intersection-union across both endpoints:

| endpoint | mean | median | 95% CI | Wilcoxon p |
| --- | --- | --- | --- | --- |
| normAP | −0.0798 | −0.0659 | [−0.1229, −0.0367] | 8.20e-05 |
| ROC-AUC | −0.0292 | −0.0171 | [−0.0457, −0.0128] | 3.38e-04 |

Both endpoints reject and both favour the **classical** kernel. Per section 8
this is "no advantage found" in its strongest form: not a failure to detect, but
a detected deficit.

**The margin, stated as D6 requires.** The effect clears the registered MDE of
0.0171 by 4.7x and its **true** primary-cell MDE of 0.0608 by **1.31x**. D6:
*"Any phrasing along the lines of 'well clear of what the arm was powered for'
is withdrawn."* That withdrawal is honoured here. The rejection does not depend
on the prior MDE, because the observed interval excludes zero on the observed
data; what the correction removes is any claim of comfortable margin.

### Fraud: no advantage found, reported as an exclusion bound

H1 does not reject:

| endpoint | mean | median | 95% CI | Wilcoxon p |
| --- | --- | --- | --- | --- |
| normAP | −0.0028 | −0.0014 | [−0.0072, +0.0017] | 0.245 |
| ROC-AUC | +0.0001 | +0.0005 | [−0.0017, +0.0019] | 0.823 |

Per section 8 this is reported as a bound and not as "no difference":

> **A true advantage larger than 0.0063 normAP at the fraud primary cell
> (SelectKBest at 8 qubits, 250 per class) is excluded at 80% power.**

**0.0063, not the 0.0059 section 8 registered.** D6: *"The fraud exclusion
bound stands, corrected from 0.0059 to 0.0063"*, that figure being the primary
cell's own paired sd of 0.0095. Section 8's registered wording is wrong and is
not quoted in the paper.

**The arm-level figure is a different quantity and is 0.0138.** D6's whole
lesson is that these two must never be interchanged: *"That compared an
arm-level registered number against a primary-cell observed one."* Any
arm-level statement about fraud quotes 0.0138.

### A unit trap, named so it is not walked into

D2's floor is *"roughly 1e-3 in average precision"*. Fraud's ROC-AUC mean of
+0.0001 is numerically below 1e-3 but is on the **ROC scale**, where the floor
does not apply. Flagging it against an AP-scale floor would be D6's conflation
in a new place. The floor is applied in this report only to normAP differences.

---

## 3. The four exploratory families

Every table below is exploratory. Section 9: no exploratory finding is evidence
for or against H1 or H2. Holm correction is within each family. The aggregation
in every tested family averages the cells at a level **within each seed** before
testing, because cells at one seed share a train/test split (`make_split` keys
on the seed alone), so each level carries 20 paired observations and not 60
pooled rows. Week 4 item 10 is the reason that is stated rather than assumed.

### Churn

| family | level | mean dNormAP | p | Holm |
| --- | --- | --- | --- | --- |
| qubit count | 4 | −0.0203 | 0.0400 | 0.1200 |
| | 6 | −0.0180 | 0.2024 | 0.2024 |
| | 8 | −0.0195 | 0.0897 | 0.1794 |
| | 10 | −0.0342 | 0.0240 | 0.0958 |
| | **12** | **−0.0659** | 9.54e-06 | **4.77e-05** |
| per mapping | **pca** | **−0.0385** | 0.0094 | **0.0189** |
| | randproj | −0.0084 | 0.3884 | 0.3884 |
| | **selectk** | **−0.0478** | 0.0020 | **0.0060** |
| training size | **100** | **−0.0268** | 0.0064 | **0.0064** |
| | **250** | **−0.0316** | 8.51e-04 | **0.0017** |
| | 50 | −0.0315 | not tested | — |

The 50-per-class arm is excluded from testing by pre-registration line 104
(*"run for the shape of the learning curve and is not used for hypothesis
testing"*) and is enforced in code rather than remembered.

**The trend that may not be claimed.** The cell-level trend is **rho −0.4692,
p 0.0777 on n = 15 cells — not significant.** The defensible statement is that
the deficit is largest at 12 qubits. "The deficit deepens with qubit count" is
not supported, and reaching for it would be week 4 items 7 and 10 repeated: a
trend inferred from a single striking level, on a unit that was already got
wrong once in this project.

### Fraud

Nothing survives anywhere. Largest magnitude +0.0045, no Holm-adjusted p below
0.19, cell-level trend rho −0.1528 p 0.5868.

Three figures are **below D2's floor and are not measurements**: qubit 10 at
−0.0008, randproj at +0.0003, training size 250 at −0.0000. They carry
`below_d2_floor` in the JSON and print as such.

### The learning curve, descriptive

Best cell per training size, corrected normAP, each arm selected independently
by inner CV.

| n/class | best quantum | best classical |
| --- | --- | --- |
| churn 50 | pca/4, 0.4631 | pca/6, 0.4609 |
| churn 100 | pca/10, 0.5534 | pca/10, 0.6044 |
| churn 250 | pca/4, 0.5853 | pca/12, 0.6137 |
| fraud 50 | selectk/8, 0.9434 | selectk/8, 0.9564 |
| fraud 100 | selectk/10, 0.9533 | selectk/12, 0.9597 |
| fraud 250 | selectk/8, 0.9632 | selectk/10, 0.9676 |

**These figures are not comparable to week 3 section 9's table** and are not
placed beside it. That table came from a 10-seed run whose records carry
`n_per_class=None` (`results/runs/classical/archive-week3-10seeds`), and it names
a method per cell, implying a post-hoc best-(cell, method) choice where this uses
`best_by_inner`. Differences run in both directions — 0.6137 here against 0.6268
there at churn 250, 0.6044 against 0.6021 at churn 100 — so no single cause is
asserted.

---

## 4. One structural reading, offered as interpretation and not as a finding

On churn the deficit is significant under PCA and SelectKBest and **not**
significant under random projection. Week 3 section 10 measured random
projection as the mapping where the classical baseline is weakest and climbs
most, 0.3678 to 0.5481 across qubit counts, the largest classical gain of any
mapping.

So the quantum kernel is competitive only where the classical baseline is worst,
and loses where it is strong. If that holds up it inverts the usual framing,
because the interesting regime is supposed to be the one where classical methods
already do well. It is exploratory, it rests on one dataset and one
non-significant contrast, and section 9 forbids it bearing on H1 or H2.

---

## 5. Verification

**An independent cross-check that the aggregation is right.** The training-size
figure for churn at 250 is −0.0316. The mean of the 15 per-cell means printed by
`report_sweep` in `results/analysis/primary_tests.log` is −0.03156. Two
different code paths, agreeing to four decimals.

**Tests.** 16 new tests in `tests/test_exploratory_sweep.py`; the full suite is
446 passing. The tests pin the within-seed aggregation against
pseudo-replication, the n=50 exclusion against drift, the Holm family size, and
the undefined-correlation case against the NaN class that has twice produced a
printed verdict here. `FLOOR` is imported from `scripts/geometric_tests.py`
rather than redefined, so `mutation_check.py`'s existing mutant on that constant
covers this use too.

**Input validation.** `--check` confirmed 15 cells and 20 seeds on all six arms
with clean pairing before any statistic was computed.

---

## 6. Corrections made this week, mine

**The learning-curve comparability claim.** The first version of
`exploratory_sweep.py` stated the family was "in week 3 section 9's form" and
"directly comparable to the classical table already published". It is neither,
for the reasons in section 3. Corrected in the caption and the docstring. The
commit message at `ad2cb5e` carries the same overstatement and is left as
written rather than rewritten.

**D2's floor was not applied.** Three fraud figures below 1e-3 were presented as
measurements, against D2's commitment that such differences *"will be reported
as such, not as a measurement"*. Every tested level now carries the flag.

**The exclusion bound was quoted at the registered figure.**
`docs/week-09-plan.md` line 96 states fraud's bound as 0.0059, quoting section 8.
D6 corrected that to 0.0063 on 25 September. The figure in this report is
0.0063; the plan document's line is wrong and is superseded here.

**Known gap, recorded rather than fixed.** `below_d2_floor` is applied to tested
levels but not to the `descriptive_only` rows, which also carry a
`mean_d_normap`. No current row is affected: churn n=50 at −0.0315 and fraud
n=50 at −0.0100 are both above the floor.

---

## 7. What week 9 still owes

* **The D14 option.** Still a DRAFT. No option among (a), (b) and (c) adopted,
  no g recomputed, no verdict moved. The declaration must be written into D14
  section 6 and pushed before any recomputed g is read.
* **The two pre-existing families are stdout only.** The 15-cell sweep and the
  per-setting comparison exist in `primary_tests.log` and nowhere structured. A
  paper table cannot be checked against a `tee` capture.
* **`primary_tests.log` is dated 25 September** and cites quantum records
  "written at commit(s): 0b796a3", a hash the 25 September history rewrite may
  have destroyed. Worth a `git cat-file -t 0b796a3`.
* **No deviation records that the deliverable became an audit protocol** while
  section 8 still describes a kernel-comparison paper. D13 is the precedent for
  declaring that before the writing rather than after.
