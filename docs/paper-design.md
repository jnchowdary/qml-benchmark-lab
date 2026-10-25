# Section 3 — Design

**Draft, 4 October 2026.** Every figure below is traceable to
`docs/pre-registration.md` v1.0. **The registered design and its later
amendments are kept separable throughout**: registered values are given first,
amendments are marked with their deviation number, and §3.9 tabulates every
movement so a reader can reconstruct the original design from this section
alone. The pre-registration is not edited; the deviations record is the
correction, as D6 established.

---

## 3.1 Data, tracks and seeds — frozen, unamended

| | churn | fraud |
| --- | --- | --- |
| source | Kaggle `blastchar/telco-customer-churn` | Kaggle `mlg-ulb/creditcardfraud` |
| SHA-256 | `88be4b93…` | `76274b69…` |
| rows | 7,032 after cleaning | 284,807 |
| features | 30 | 29 (`Time` dropped) |
| positives | 1,869 | 492 |

**Seeds** 0 to 19, fixed in `qbench.data.SEEDS`, chosen from measured paired
variance: at ten seeds churn's minimum detectable effect was 0.0324, larger than
almost any effect this literature reports.

**Tracks.** *Matched* — class-balanced subsample, mapped to `n_qubits`
dimensions, scaled to [0, π] — is the hypothesis-testing track and **the only
one on which g can be computed**, since g requires both Gram matrices over the
same points. *Unconstrained* is a reference ceiling, reported separately and
never mixed into a paired test.

**Registered limitation, uncorrected.** Seeds resample one fixed dataset, so
splits overlap and paired differences are not strictly independent. Expected
shared test positives between two seeds: ~3 of 75 on churn (4%), ~11 of 75 on
fraud (15%, because 250 positives per class are drawn from only 492 available).
**The tests are therefore mildly anti-conservative on fraud**, which was stated
in advance rather than discovered afterwards.

---

## 3.2 The grid — 360 units

Three mappings (PCA, Gaussian random projection, SelectKBest on mutual
information, seeded) × five qubit counts (4, 6, 8, 10, 12) × three training
sizes (50, 100, 250 per class) × four quantum settings × two datasets = **360
units**, each observed over 20 seeds: 7,200 per-seed rows.

**Quantum kernels, frozen.** PennyLane embedding kernels — angle and IQP
embeddings, each at 1 and 2 repetitions — on `lightning.qubit`. **All four run;
none is screened out before the sweep.** The registered reason is explicit and
is the design decision most worth preserving: an earlier version used g to
reduce the quantum grid, which is circular, because conditioning the experiment
on g and then testing whether g predicts the outcome cannot answer the question.
The cost of refusing that shortcut was about 46 hours of compute against 34.

**Classical kernels and grids, frozen.** Linear; RBF with gamma 1e-3 to 1e2 in
half-decades; polynomial with degree 2 to 5, scale-relative multiplier
0.1/1/3/10, `coef0` in {0, 1}; C from 1e-4 to 1e4. These were tested for
under-tuning by extension in both directions against a shuffled-label null. The
extension gained more on random labels than on real ones on every kernel and
both datasets, by factors of 2.0 and 5.0 on churn and 35.7 and 6.6 on fraud, so
they stand. §3.7 records that the registered wording gives this as "five to
seven times", which is the polynomial-kernel figure and not the range.

**Tuning, identical across arms.** Nested cross-validation: 20 outer seeds,
5-fold stratified inner CV on the outer-train portion only.
`SVC(kernel="precomputed", class_weight="balanced")` for every kernel, classical
and quantum alike, **so folds, solver and selection rule are identical and only
the Gram matrix differs**. Selection on inner-CV average precision. Grid points
failing to converge within 1,000,000 iterations are excluded, never scored.

**Primary cells**, named in the registration so they could not be chosen later:
**churn = PCA at 12 qubits; fraud = SelectKBest at 8 qubits**, both at 250 per
class. These are the cells where the *classical* baseline is strongest, which is
deliberately the hardest test for a quantum advantage.

---

## 3.3 Hypotheses

**H1 — no quantum advantage in the primary cell.** Per dataset, the paired
per-seed difference between best quantum and best classical kernel in the
pre-specified primary cell is zero. Two-sided, one test per dataset.

**H2 — the geometric difference carries no information.** Across all 360 units,
g_λ(K_C‖K_Q) has no monotone relationship with the observed quantum-minus-
classical difference. Two-sided, though Huang et al.'s predicted direction is
positive. *The registration states plainly that "H2 is the reason this project
exists. H1 is the benchmark it is embedded in."*

**H3 — g has no negative predictive value.** Among units with g_λ below 2, the
observed difference is not bounded nearer zero than among units above it.

> **Amended, D13.** As registered, H3 was *"confirmatory but subordinate to H2
> and reported only if H2 is rejected."* H2 was not rejected, so under the
> registration as written H3's result should not have been reported. It was
> ungated in week 4 for a stated reason, the departure was not recorded in
> `deviations.md` until 29 September — after H3's result was computed and
> published — and D13 therefore offers the reader two readings and does not
> choose between them. §4 reports H3 under both.

---

## 3.4 Endpoints and the decision rule — unamended

Two co-primary endpoints, both from the same stored per-test-point decision
scores:

- **normAP** = (AP − chance) / (1 − chance), where *chance* is the exact
  expected average precision of a random ranking at that test-set size and
  positive count — **not the base rate**. A random ranker scores 0.5516 on 30
  balanced test points and 0.5154 on 150, so comparing raw AP across test-set
  sizes compares two different nulls.
- **ROC-AUC**, which has an exact null of 0.500 at any sample size.

**Decision rule: intersection-union.** A hypothesis is rejected only if **both**
endpoints reject at α = 0.05, two-sided. No alpha correction, because the type I
error of "reject only if both reject" is at most that of either test alone.

This was chosen by measurement. The two endpoints' paired differences correlate
at a median of 0.818 to 0.947 across the matched arms, so requiring both costs
4 to 8% on the minimum detectable effect against 12% for splitting alpha across
a union rule.

**Test statistic.** Wilcoxon signed-rank on the 20 paired per-seed differences,
two-sided; paired t reported alongside as a sensitivity check. Records are
paired on the **test-label fingerprint**, asserted equal before any test runs;
a mismatch aborts the analysis rather than being worked around.

---

## 3.5 Power — registered, and corrected

**As registered** (minimum detectable effect at 80% power under the
intersection-union rule, from the measured median paired sd in each arm):

| arm | paired sd | MDE single endpoint | MDE intersection-union |
| --- | --- | --- | --- |
| churn 50/class | 0.0604 | 0.0399 | **0.0427** |
| churn 100/class | 0.0424 | 0.0280 | **0.0298** |
| churn 250/class | 0.0241 | 0.0159 | **0.0171** |
| fraud 50/class | 0.0237 | 0.0157 | **0.0163** |
| fraud 100/class | 0.0136 | 0.0090 | **0.0094** |
| fraud 250/class | 0.0085 | 0.0056 | **0.0059** |

> **Amended, D6. Every row above is wrong, in the same direction, by 2.3x to
> 3.9x.** The registered standard deviations pair *classical kernels against
> each other* — `power_analysis.py` was written in week 3, when the classical
> arm was the only arm that existed, so it could not have measured anything
> else. H1 tests a cross-arm difference, which is both larger and more variable.
>
> **Corrected, arm level** (the quantity the registered table reports):
> churn 250 → **0.0608**; churn 100 → **0.1005**; churn 50 → **0.1368**;
> fraud 250 → **0.0138**; fraud 100 → **0.0365**; fraud 50 → **0.0571**.
>
> **Corrected, primary cell** (the quantity an exclusion bound must quote):
> churn PCA/12 → **0.0608**; fraud SelectKBest/8 → **0.0063**.
>
> These are different quantities and D6 records that conflating them is how its
> own first version went wrong. **Every statement of the form "a null here would
> exclude effects larger than X" in the registration is superseded.**

**Registered as underpowered in advance.** The 50-per-class churn arm resolves
only 0.0427 and would need 74 seeds to reach 0.020; it is run for the shape of
the learning curve and **not** used for hypothesis testing. D6 makes this
further true — it actually resolves 0.1368, three times coarser than the figure
that already disqualified it.

---

## 3.6 How g is computed

**As registered.** g in its regularised form, `geometric_difference_regularised`,
on normalised Gram matrices over the matched-track training set. λ derived from
the classical model actually being compared against, via
`lambda_from_svm_C(C, n) = 1/(2·C·n)`, using the C that inner CV selected for
that cell. A λ sweep reported alongside every value, because g is sensitive to λ
and an unregularised g exceeding its own √n ceiling means the classical kernel
is under-regularised, not that the quantum kernel separates strongly.

> **Amended, D5.** The λ-from-C value is no longer the reported quantity. A
> **frozen sweep** at λ ∈ {1e-1, 1e-2, 1e-3, 1e-4} is reported with λ-from-C
> alongside, a **per-seed ceiling rule** excludes and counts any seed whose g
> exceeds √n at a given λ, and **the registered conclusion stands only if sign
> and significance agree at every λ with no ceiling breach**. D5 is a
> strengthening: requiring agreement across four λ is strictly harder than
> picking one, and it cannot be gamed toward a positive result.
>
> **Amended, D7 and D8.** A unit's g is the **median** over surviving seeds, not
> the mean, with the IQR reported and a 10-seed minimum; the observed difference
> is averaged over **the same** surviving seeds; the above-precision-floor
> subset must agree; and a signed secondary is pre-declared.
>
> **Open, D14 (draft).** `lambda_from_svm_C` returns 1/(2·C·n) with a docstring
> asserting the correspondence and citing nothing. Huang prints no SVM-to-ridge
> relation, and his Appendix D objective is a summed residual, which points to
> 1/(2C). **The frozen sweep carrying every reported result is unaffected; the
> λ-from-C column is not.** D14 remains undecided and nothing has been
> recomputed.

**H2 test.** Spearman rank correlation between g_λ and the observed mean paired
difference in normAP across all 360 units. Two-sided, α 0.05, single test;
per-dataset results are a pre-declared secondary.

**H3 test.** Units split at g_λ = 2 — **fixed in the registration and not tuned
afterwards** — comparing |observed difference| above and below the split by
Mann-Whitney U, two-sided, α 0.05.

---

## 3.7 Controls — registered, all executed

**Label-shuffled negative control.** The full quantum pipeline on permuted
labels at each primary cell. Expected ROC-AUC 0.500 and normAP 0; a consistent
excess in both beyond about two seed-level standard errors **halts the
analysis**. §4 reports it clean on both datasets.

**Chance floor.** Every normAP against exact chance, never the base rate,
enforced in code and tested.

**Grid adequacy.** Any claim that a quantum grid is too narrow must be
adjudicated by `scripts/check_grid_edges.py` against a shuffled-label null.
**Hyperparameter edge flags alone will never justify widening a grid**, because
extension raises the maximum inner-CV score even when no point is better.

The registered wording puts that effect at "five to seven times the real gain on
the classical grids". The measurement supports its direction everywhere and its
range nowhere. Five and seven are the polynomial-kernel mean ratios, 5.0 on
churn and 6.6 on fraud; on the RBF kernels the ratio is 2.0 on churn and 35.7 on
fraud, so two of the four measurements fall outside the registered range and one
of them falls below it, understating the effect the rule exists to guard
against. The figures are in `results/analysis/grid_edges_*_both*.json`. **The
pre-registration's wording is unamended**, because changing a registered
document is a deviation and not a copy edit.

**Backend.** All quantum kernels on `lightning.qubit`, with a test asserting
`default.qubit` agreement to 1e-8. Cost is reported in circuit evaluations,
which are framework-independent; wall-clock is secondary and always labelled
with its backend.

> **Amended, D12.** The IBM hardware runs registered for weeks 7 to 8 were
> **never feasible as registered**, which is the wording D12's amendment
> requires in place of "dropped". The run needs 18,172,000 circuit executions,
> 113,575 per record across four settings, twenty seeds and two datasets,
> against an Open Plan allocation of ten minutes of QPU time per month.
>
> **Corrected, D18.** Those are circuit counts and not costs. A hardware run
> estimates each kernel entry from S shots, so the executions IBM meters are the
> circuit count times S; at the 1,024 shots this project's one audited hardware
> deposit used, a single primary-cell Gram is 116,300,800 executions against a
> documented per-job ceiling of 10 million, and the registered scope is
> 18,608,128,000. D12's figure of thirty times the budget omitted the shot
> dimension, as did its finding that one Gram would have fitted inside the
> allocation; the second is withdrawn. The registered run was further from
> feasible than D12 said, not nearer.
> Nobody established this for seven weeks, although the number that makes the
> timeline impossible was printed in every quantum record from week 4 and three
> weekly records each flagged the allocation as unchecked. No registered claim
> depends on them, and the protocol has consequently never been run against this
> project's own hardware records because there are none — a gap in the
> protocol's evidence base, recorded as forgone rather than unimportant.

---

## 3.8 The registered exploratory set

Section 9 of the registration fixes the confirmatory set at **exactly three
tests**: H1 on churn, H1 on fraud, H2. No correction across the H1 pair, because
they are separate questions about separate datasets.

Everything else is exploratory — *"the 15-cell sweep per dataset, the
qubit-count trend, the learning curve, the training-size comparison, per-mapping
breakdowns"* — reported with **Holm-corrected p-values within each family**,
labelled exploratory in every table caption, with **no exploratory finding
described as evidence for or against H1 or H2**.

**Search-size asymmetry, declared in advance.** The classical side searches 396
grid points per cell, the quantum side 36 — an order of magnitude wider. The
registration states this favours the classical side on inner-CV scores and not
on the outer test estimate, which is what the tests use, and requires the
comparison be reported **both** as best-quantum-of-four against
best-classical-of-three **and** per quantum setting against the best classical
kernel, so a reader can see whether the headline depends on the quantum side
getting to choose.

---

## 3.9 Every movement from the registered design, in one table

| # | what moved | direction |
| --- | --- | --- |
| D2 | a measured precision floor of ~1e-3 in AP added; differences below it reported as unresolvable | adds a constraint |
| D5 | reported g becomes a frozen λ sweep with a per-seed ceiling rule; conclusion must hold at every breach-free λ | strictly harder |
| D6 | the registered power table is wrong by 2.3x–3.9x throughout; corrected figures supersede it | weakens claims |
| D7 | unit g is the median over surviving seeds, IQR reported, 10-seed minimum | adds a constraint |
| D8 | observed difference averaged over the same surviving seeds; above-floor subset must agree; signed secondary pre-declared | adds a constraint |
| D12 | IBM hardware runs never feasible as registered: 18.17M circuits against a 600-second monthly allocation | removes planned evidence |
| D13 | H3 ungated from H2, declared after its result was published; two readings offered | weakens H3's status |
| D14 | `lambda_from_svm_C` corrected to 1/(2C) on an outcome-to-verdict mapping pushed before the re-run; the supplementary column's breaches fall from 2,893 to 979 of 7,200 and no verdict moves | corrects a defect, changes no result |
| D15 | the paper's organising contribution becomes the protocol | reframes, changes no analysis |
| D16 | Huang's own g_tra selection over his declared grid, specified in full before computation; a **prospectively specified follow-up analysis**, never confirmatory | computed, **outcome B3**: unsatisfiable on 76.5% of units, reported unresolved, no verdict moves |

**Nothing in this table changes a hypothesis, an endpoint, a decision rule, a
threshold, or a result.** D6 and D13 weaken what may be claimed; D2, D5, D7 and
D8 make the tests harder to pass; D12 removes evidence that was never collected;
D14 corrected one supplementary column's λ definition under a pre-committed
mapping and left every verdict where it was; D15 is editorial; D16 ran under a
pre-commitment published first, returned B3, moved no verdict, and cannot by its
own terms become part of the confirmatory design.
