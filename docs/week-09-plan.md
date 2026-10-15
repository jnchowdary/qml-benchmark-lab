# Week 9 remaining, and weeks 10 to 12

**Date:** 1 October 2026.
**Method:** every item below was checked against the repository today, not
recalled. Where something is already done it is marked done with its figures, per
the operational rule added to `week-09-opening.md`.

The registered timeline, section 13 verbatim: *"Week 9: statistics and the
exploratory sweep. Weeks 10 to 12: writing."*

---

## 1. What is already done, with the numbers

**H1 is complete on both datasets, at all three training sizes.**
`results/analysis/primary_tests.json`, six entries, intersection-union rule at
alpha = 0.05.

| dataset | n/class | cell | confirmatory | reject | normAP median | p (Wilcoxon) |
|---|---|---|---|---|---|---|
| churn | 250 | pca, 12 | yes | **yes** | **−0.0659** | **8.20e-05** |
| fraud | 250 | selectk, 8 | yes | no | −0.0014 | 0.245 |
| churn | 100 | pca, 12 | no | no | −0.0185 | — |
| fraud | 100 | selectk, 8 | no | no | −0.0042 | — |
| churn | 50 | pca, 12 | no | no | −0.0220 | — |
| fraud | 50 | selectk, 8 | no | no | +0.0000 | — |

The churn result is not a null. Both endpoints reject and both point the same
way: normAP mean −0.0798, 95% CI [−0.1229, −0.0367]; ROC-AUC mean −0.0292, CI
[−0.0457, −0.0128], p = 3.38e-04. **That is a measured classical advantage of
about 6.6 points of normAP at the median, in the cell chosen because it was the
classical baseline's strongest.** Fraud is a clean null and takes section 8's
exclusion-bound phrasing.

**The registered label-shuffled quantum negative control is clean on both
datasets.** `results/analysis/negative_control_quantum.log`: churn ROC-AUC mean
0.5058 at +0.52 sigma from 0.500 with the AP residual at +0.45 sigma; fraud
0.5001 at +0.01 sigma with the residual at −0.09 sigma. Section 7's halt
condition is not met. This is the control Flórez Ablan et al.'s released code
does not contain.

**H2 and H3 are executed and return NOT ESTABLISHED** across all 360 units, with
the dependency structure recorded in D5's correction and in `week-09-opening.md`.

**The exploratory sweep's raw data already exists.** `results/runs/quantum/`
carries `churn_matched_n250.jsonl` with all **15 cells** (3 mappings x 5 qubit
counts) at 80 records each, plus `n100` and `n50` files, and the same for fraud.
Nothing needs recomputing to build the sweep.

**Holm correction is already implemented**, in `scripts/audit.py`,
`scripts/primary_tests.py` and `scripts/rbf_surrogate.py`. Section 9's
requirement does not need new machinery.

**D12 records the IBM hardware drop**, so weeks 7 to 8 departing from the
registered timeline is already declared.

---

## 2. Week 9: what is actually left

### 2.1 The exploratory sweep, assembled and corrected

Section 9 names five families and requires each to be *"reported with
Holm-corrected p-values within each family, labelled exploratory in every table
caption"*, with *"no exploratory finding described as evidence for or against H1
or H2"*. Checked today: **no output exists for four of the five.** A search of
`results/` and `docs/` for `qubit`, `learning`, `training_size` and `mapping`
returns nothing; the only `sweep` matches are unrelated logs.

So the work is assembly, not computation:

1. the 15-cell sweep per dataset
2. the qubit-count trend
3. the learning curve
4. the training-size comparison
5. per-mapping breakdowns

The training-size family is partially served by `primary_tests.json`, which has
n50/n100/n250 but **only at the primary cell**. The other 14 cells per dataset
are uncovered.

### 2.2 Section 9's two-way comparison, which is not optional

> *"The comparison is reported both as best-quantum-of-four against
> best-classical-of-three and per quantum setting against the best classical
> kernel, so a reader can see whether the headline depends on the quantum side
> getting to choose."*

`primary_tests.json` stores `quantum_chosen` and `classical_chosen` counts — for
churn n250, angle-r1 won 16 of 20 seeds and poly won 15 — which is the ingredient
but not the per-setting comparison. That second reporting mode has not been
produced and the registration requires it.

### 2.3 Section 8's reporting language

Fraud must be written as *"an advantage larger than ... 0.0059 on fraud is
excluded at 80% power"*, not as "no difference". Churn must be written with the
effect size and its interval, as a rejection in the direction of classical
advantage. Neither phrasing exists in a report yet.

### 2.4 The D14 decision and the lambda work

In order: choose among (a), (b), (c); write the choice and the full
outcome-to-verdict mapping into D14 section 6; commit and push; then implement;
then run. D14's risk analysis needs revising first, because under the design
settled on 1 October — frozen sweep as the only input to `clean`, everything else
reported beside it — no candidate option can flip the verdict, which makes D14
section 1 overstate the risk.

Before building the Huang column, compute `g_tra` on a stratified sample. It is
cheap, needs no `g`, and distinguishes three outcomes: the rule selects the grid
top for most units and the column approximately duplicates lambda = 0.1; the rule
selects a spread and the column is informative; or no grid lambda is admissible
and the rule returns nothing. The mapping in D14 needs a branch for the third.

### 2.5 The Flórez Ablan interpretation check

Their e-print source, arXiv:2503.05602, read the way Huang's was. Until then
D14 forbids any outward statement about their paper's interpretation. This is the
only claim from the 30 September work still resting on a truncated retrieval.

---

## 3. Weeks 10 to 12: writing, and the state of it

**Checked today: there is no paper draft and there are no figures.**
`docs/` contains no paper or manuscript file, and `results/figures/` contains
**zero files**. Three of twelve registered weeks are allocated to writing and
none of it has begun.

### 3.1 The paper's spine, as section 8 determines it

Section 8: *"g not validated. H2 not rejected. Given 360 units, this would be a
meaningfully powered negative result about a metric the field currently takes on
trust, and the paper leads with it."*

That is the registered lead and the result obtained. Beneath it: H1 finds no
quantum advantage anywhere, with a significant classical advantage on churn and
an exclusion bound on fraud; the negative control is clean; the exploratory sweep
is context only.

### 3.2 The one structural change that is not recorded anywhere

Searched today: `docs/deviations.md` runs D1 to D14 and **none of them records
that the project's deliverable changed.** `docs/audit-protocol.md` exists at 184
lines and is referenced throughout the deviations record, but only incidentally.
Section 8 still describes a kernel-comparison paper and says *"the paper is
written the same way in each case"*.

If the paper leads with the audit protocol and uses churn and fraud as the worked
example, that is a departure from section 8 and section 11 requires it be
recorded with its date and whether it was decided before or after the results
were seen. **D13 is the precedent and the warning**: H3 was ungated in week 4 for
a good reason, the reason was never written into `deviations.md`, and when it was
finally declared on 29 September the lateness cost it a confirmatory reading. The
framing change should be declared before the writing starts, not justified after
a reader notices the paper is not the one registered.

### 3.3 The mechanical items

- **All ten `.docx` exports are stale.** `docs/deviations.docx` is from 22:31 on
  29 September and `deviations.md` has had D13 and D14 appended since;
  `week-04-report.docx` is from 17:56 on 29 September and predates the week-4
  resolution appended on 30 September. Week 7 section 10 already flagged two of
  these as outstanding. There is no `week-09` export. Regenerate all from
  `scripts/report_to_docx.js` once the markdown is final, not before.
- **Software Heritage snapshot.** D11's second amendment records that this gives
  no retrospective evidence, because the pre-registration and the results sit in
  the repository simultaneously, and that its value is forward-looking only. It
  would make weeks 9 to 12 externally witnessed, which is the only external
  timestamp this project can still obtain.
- **`prerewrite-20260925`** remains local by choice. If the paper cites the two
  pre-registration hashes, the paper must say they resolve only on that branch.

### 3.4 Loose ends that could undermine the paper if left

- the churn tuned-arm seeds, four outstanding
- the grid adequacy check

Both are small and both sit under results the paper will quote.

---

## 4. The schedule risk, stated plainly

Week 9's analysis has not started, weeks 10 to 12 have no draft and no figures,
and the registered timeline ends at week 12. The computation is almost entirely
done; what remains is assembly, correction, declaration and prose, which is the
part that cannot be parallelised and the part this project has repeatedly found
takes longer than expected because each pass surfaces a defect in the last one.

The sequencing that protects the record: declare the framing change and settle
D14 **before** building the exploratory tables, because both decide what the
tables are allowed to say. Figures after the tables. Exports last. Nothing
regenerated into `.docx` until the markdown it derives from is final, since
stale exports contradicting their sources is already a recorded defect of this
project rather than a hypothetical one.
