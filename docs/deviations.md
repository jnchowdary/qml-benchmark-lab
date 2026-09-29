# Deviations from the pre-registration

Required by `docs/pre-registration.md` section 11. Every departure is recorded here with its date, its reason, and **whether it was made before or after the affected results were seen**. A deviation made after seeing results is not forbidden, but the affected analysis is labelled exploratory.

---

## D1. Fidelity kernels computed from statevectors rather than pairwise circuits

**Date:** 25 September 2026. **Made before any real quantum result existed.** At the time of this change the only quantum runs in the project were the label-shuffled negative controls; no quantum kernel had been evaluated on unpermuted labels on either dataset.

**What the pre-registration describes.** Section 3 registers PennyLane fidelity kernels on `lightning.qubit`. Section 7 reports cost in circuit evaluations. The implied protocol, and the only one available on hardware, is to run U(x_i)† U(x_j) for each pair and measure the all-zeros probability: n(n−1)/2 circuit evaluations per Gram matrix.

**What is done instead.** On a simulator the embedded statevectors can be extracted directly, so the whole Gram follows from n executions and one matrix product: K = |Ψ Ψ†|².

**Why.** The pairwise protocol was measured at 110 hours for the registered sweep, against a budgeted 46. The budget was wrong because `benchmark_backends.py` timed only `angle-r1`, the cheapest of the four frozen settings; at 12 qubits the four span 1.11 to 5.06 ms per statevector. The statevector formulation brings the sweep to about one hour.

**Evidence it changes nothing.**

* Gram matrices agree with the pairwise protocol to 1.3e-15 to 1.4e-14 on the real primary cells of both datasets, all four settings, square and rectangular blocks (`results/analysis/statevector_gap_*.log`).
* Unit tests assert agreement below 1e-12 at 4 and 8 qubits for every frozen setting (`tests/test_quantum_path.py`).
* The negative-control verdicts reproduce the pairwise run to four decimal places on both datasets: churn +0.52 and +0.45 sigma, fraud +0.01 and −0.09 sigma, including the same worst cells.

**What is NOT changed.** Reported cost stays hardware-equivalent. `QuantumGramFactory.evaluations()` reports n(n−1)/2, which is what a quantum computer would need; `simulator_executions()` reports the shortcut separately. The paper must not claim quantum kernels are cheap on the strength of something no quantum computer can do. The IBM hardware runs in weeks 7 to 8 use the real pairwise protocol and are unaffected.

---

## D2. Numerical precision floor on every quantum result

**Date:** 25 September 2026. **Recorded before any real quantum result existed.** This is a measured property of the problem rather than a change to the design, but it bounds what any quantum result can claim and so belongs here rather than only in a weekly record.

**The measurement.** The quantum Gram matrices on the primary cells are numerically singular: cond(K_train) from 4.2e16 to 2.4e19, with smallest eigenvalues at ±1e-15. Feeding two arithmetically identical kernels that differ only at machine precision into `SVC(kernel="precomputed")` produces decision functions that differ by:

| C | largest score difference |
| --- | --- |
| 0.01 | 1e-16 to 7e-16 |
| 1 | 1e-14 to 7e-4 |
| 100 | 1e-14 to 2e-3 |
| 10,000 | 7e-4 to 6.3e-2 |

The dual solution of an SVM on a near-singular kernel at large C is underdetermined; both solutions are equally optimal. This is not an implementation defect and is not specific to either kernel formulation. The pipeline itself is deterministic: the same code run twice gives byte-identical results (0.00e+00, sixteen of sixteen).

**Consequence, and why the registered design survives it.** Rank correlation between the two solutions is 1.000000 almost everywhere, worst case 0.999982. **Orderings are stable even where raw scores are not.** Both registered endpoints — normalised average precision and ROC-AUC — are rank statistics, so they move by under 1e-3, and the registered test (Wilcoxon signed-rank on paired per-seed metric differences) operates on those. The design is unaffected.

**What this rules out.** Any test on thresholded predictions, McNemar in particular, is not usable on this pipeline: a machine-precision perturbation can flip individual predictions. McNemar is named as a motivation for storing per-test-point scores in `docs/week-03-report.md` section 6; it is not a registered test, and it will not become one.

**What must be reported.** Every quantum result in this project carries a precision floor of roughly 1e-3 in average precision, set by kernel conditioning. Against fraud's minimum detectable effect of 0.0056 that is 18%, and against churn's 0.0171 it is 6%. Any quantum-minus-classical difference smaller than 1e-3 is below the arithmetic resolution of the pipeline and will be reported as such, not as a measurement.

---

## D3. Section 8 does not name the outcome that actually occurred

**Date:** 25 September 2026. **Recorded at the moment the primary tests were first run, before any further analysis and before the week-4 record was written.** This is a defect in the registered document, not a change to the design, and it is recorded here because a reader must be able to see that it was recognised immediately rather than resolved later in whichever direction suited the paper.

**The defect.** H1 is two-sided: "the paired per-seed difference between the best quantum kernel and the best classical kernel, in the pre-specified primary cell, is zero." A two-sided test has three outcomes. Section 8 names two of them — *advantage found* (both endpoints reject and the difference favours the quantum kernel) and *no advantage found* (failure to reject) — and is silent on the third, where both endpoints reject and the difference favours the **classical** kernel.

**What occurred.** On churn, in the registered primary cell (PCA at 12 qubits, 250 per class), both endpoints reject and the difference favours the classical kernel: normAP −0.0798 (95% CI −0.1229 to −0.0367, Wilcoxon p = 8.2e−05) and ROC-AUC −0.0292 (95% CI −0.0457 to −0.0128, p = 3.4e−04). On fraud, in its primary cell (SelectKBest at 8 qubits), neither endpoint rejects.

**How it is resolved, and why the resolution is not a choice.** No rule is being invented after the fact. The decision rule in section 4 is untouched: intersection-union, both endpoints, alpha 0.05, two-sided, Wilcoxon. That rule determined the rejection. What section 8 omitted was only the *label* for a rejection in the negative direction, and there is exactly one label consistent with the registered direction convention:

> **Disadvantage found.** Both endpoints reject in a primary cell and the difference favours the classical kernel. Reported with the effect size and its confidence interval, symmetrically with *advantage found*, and never as a null result.

The symmetry is the whole point. Had the same magnitude appeared with the opposite sign it would have been reported as an advantage, so it is reported as a disadvantage with the same prominence and the same effect size.

**What is explicitly NOT done.** The result is not downgraded to "no advantage found", which would be a false null. The primary cell is not reinterpreted. The direction of H1 is not retrospectively made one-sided, which would change the alpha the test was run at. The pre-registration is not edited: version 1.0 stands as registered, defect included, and this record is the correction.

**Standing caveat this creates.** Because the label was added after the sign was known, the *label* is a post-hoc element of the analysis even though the test that produced it was not. Any statement of the churn result in the paper carries a pointer to this record.

---

## D4. An exploratory bandwidth arm for the quantum kernel

**Date:** 25 September 2026. **Made AFTER the registered sweep was seen, and after H1 was tested.** This is the most consequential deviation in the project and it is post-hoc in the fullest sense: the registered quantum arm lost on churn, and this arm exists because of a defect that loss exposed. Everything it produces is exploratory. This record is written, and the grid below frozen, **before the arm is run**.

**The defect in the registered design.** Section 3 freezes the quantum grid as embedding family (angle, IQP) × repetitions (1, 2), with C tuned over nine values. It does not tune the embedding bandwidth. `qbench.features.scale_to_angles` fixes the feature range at [0, π] and nothing in the pipeline varies it. The classical arm, meanwhile, tunes RBF gamma over eleven values spanning five decades, and polynomial degree and scale-relative multiplier besides.

This is not the search-size asymmetry declared in section 9. That declaration concerns grid point counts and inner-CV optimism, and argues the wider classical search flatters classical inner scores without affecting the outer test estimate the tests use. The present issue is different in kind: bandwidth is a **shape parameter of the kernel that the quantum arm cannot vary at all**, and it is the parameter most directly implicated in whether a fidelity kernel functions at more than a handful of qubits, because too large a bandwidth drives the Gram matrix toward the identity and too small drives it toward all-ones.

**The registered results themselves indicate the grid stops on the wrong side of a boundary.** For the angle family, `reps` is a bandwidth parameter in disguise: two applications of `AngleEmbedding` is one application at twice the angle, an identity now asserted by a test. So the registered grid searches effective scale factors 1 and 2, and nothing below 1. Across both datasets, all three training sizes and both embedding families, the smaller scale won **twelve comparisons out of twelve**, monotonically:

| arm | angle-r1 | angle-r2 | iqp-r1 | iqp-r2 |
| --- | --- | --- | --- | --- |
| churn 250 | −0.0606 | −0.0959 | −0.1011 | −0.3008 |
| churn 100 | −0.0152 | −0.1112 | −0.0279 | −0.2734 |
| churn 50 | +0.0032 | −0.1415 | +0.0013 | −0.2346 |
| fraud 250 | −0.0028 | −0.0164 | −0.0125 | −0.0172 |
| fraud 100 | −0.0002 | −0.0188 | −0.0158 | −0.0237 |
| fraud 50 | −0.0128 | −0.0285 | −0.0077 | −0.0358 |

A one-parameter family, a monotone ordering, and the boundary of the searched range at the better end. Section 7 states that hyperparameter edge flags alone will never justify widening a grid, and that rule is respected: the flags are not the argument, and widening is adjudicated below against a shuffled-label null exactly as the classical grids were.

**What is run.** Bandwidth becomes a kernel hyperparameter selected by inner CV **inside** each embedding family, which is precisely how the classical arm selects RBF gamma. Each family still writes one record, so the record shape and every downstream analysis are unchanged. The grid, frozen here:

`BANDWIDTH_GRID = (0.0625, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0)`

Powers of two bracketing the registered value **on both sides**, so the registered kernel is nested inside the grid rather than replaced by it, and so the extension cannot be accused of going only in the direction that helps. A test asserts 1.0 is in the grid and that the grid spans both sides of it.

**What is not touched.** The classical arm is not re-tuned; its grids stay frozen. The registered quantum files are not modified or reinterpreted: the arm writes to separate `_bw` files. Bandwidth 1.0 is asserted by test to reproduce the registered kernel exactly, so the registered records and the H1 verdict stand as computed. Pre-registration v1.0 is not edited.

**How it is adjudicated, fixed in advance.** Widening any grid raises the maximum inner-CV score even when no searched point is genuinely better, and on the classical grids that effect was measured at five to seven times the real gain on shuffled labels. So the bandwidth arm is run **twice**, on real labels and on permuted labels, and the quantity that decides anything is the gain from widening on real labels *relative to* the gain from widening on permuted labels. If widening buys as much on noise as on signal, it is winner's curse and will be reported as such.

**What each outcome licenses, stated before the numbers exist.**

* *The gap closes and the gain exceeds the shuffled-label gain.* Then the registered H1 rejection on churn is a result about fixed-bandwidth quantum kernels and not about quantum kernels, and the paper must say so in those words. H1 as registered still stands as computed; it is its interpretation that narrows. The bandwidth-tuned comparison is reported as exploratory, with no p-value presented as confirmatory, and the honest headline becomes the bandwidth finding itself.
* *The gap closes no more than it closes on permuted labels.* Then the registered result stands unqualified, the widening is shown to be winner's curse, and this arm becomes a control strengthening H1 rather than a threat to it.
* *The gap widens or the selected bandwidth is 1.0 throughout.* Then the registered grid was adequate at the registered scale and the twelve-out-of-twelve ordering above is explained by something other than bandwidth, which must then be identified rather than left as a loose end.

**Standing caveat.** Because this arm was designed after the registered outcome was known, no result from it may be reported as confirmatory, and no p-value from it enters the confirmatory family of section 9. Every table drawn from the `_bw` files carries a pointer to this record.

---

## D5. How lambda is handled in the test of H2 — IN FORCE from 25 September 2026

**Date:** 25 September 2026. **Made after the registered sweep and after H1, but before H2 has been tested at all.** Unlike D1 to D4 this changes how a REGISTERED HYPOTHESIS is tested rather than adding an exploratory arm, so it was drafted and held rather than applied.

**Approval.** Drafted and presented in full, with the problem, the proposal, the frozen sweep and the three licensed outcomes, on 25 September 2026. Approved by Nagesh Chowdary the same day in conversation, after the alternative (keeping the registered lambda-from-C rule) had been shown to return g = 57.3 for a kernel provably equal to an RBF. The approval was given as assent to proceed rather than as a line-by-line review, which is recorded here plainly; if that was not the intent, this record reverts to DRAFT and no week-5 result computed under it stands.

**The problem, measured.** Section 6 sets lambda from the classical model being compared against: `lambda_from_svm_C(C, n) = 1/(2*C*n)`. The point of that rule was to remove a free parameter. It does not survive contact with the data, because the classical arm's inner CV reaches the top of the C grid: C = 1e2 on churn and 1e3 on fraud in the primary cells, giving lambda near 1.4e-6, at which g diverges. Measured on the primary cells, 8 seeds each:

| lambda | churn g at bandwidth 1.0 | churn g at selected bandwidth | fraud g at 1.0 | fraud g at selected | cells above the sqrt(n) ceiling |
| --- | --- | --- | --- | --- | --- |
| from C (registered) | 5.979 | 2.529 | 24.518 | 3.708 | 2/8 churn, 4/8 fraud |
| 1e-1 | 2.470 | 1.922 | 3.802 | 1.471 | 0 |
| 1e-2 | 6.748 | 2.101 | 10.182 | 1.593 | 0 churn, 2/8 fraud |
| 1e-3 | 19.796 | 2.287 | 32.103 | 2.746 | 6/8, 8/8 |
| 1e-4 | 42.954 | 2.366 | 87.554 | 3.334 | 7/8, 9/8 |

g above the sqrt(n) ceiling of 18.71 means the classical kernel is under-regularised in the g computation and the value says nothing about the kernels. The single worst case makes the point: churn seed 2 is an angle kernel agreeing with an RBF to 2.3e-4 in Gram RMSE and ranking every pair identically (Spearman 1.000000), and its g at lambda-from-C is **57.3**. The most provably classical kernel in the study carries the largest geometric difference. That is a measurement of lambda, not of geometry.

**What must NOT be done.** Pick the lambda that makes g well behaved. 1e-1 gives no breaches on either dataset and would be the obvious choice, and choosing it after seeing that would be selecting a hyperparameter to make a statistic behave, which is the same class of error as widening a grid because the result improves. It would also be unfalsifiable: g at a single hand-picked lambda can be made to say almost anything.

**Proposed handling.** Test H2 across a fixed lambda sweep and require consistency, rather than at one lambda:

* The sweep is frozen as `(1e-1, 1e-2, 1e-3, 1e-4)` plus lambda-from-C, reported in full for every unit.
* H2's Spearman correlation is computed at each lambda separately. **The registered conclusion stands only if the sign and the significance agree across every lambda at which no unit breaches its ceiling.** Where they disagree, the reported finding is that g's relationship to observed performance depends on the regularisation chosen, which is itself a substantive result about the metric's usability as a pre-training screen.
* Units whose g exceeds the sqrt(n) ceiling at a given lambda are excluded at that lambda and the exclusion count is reported, never silently dropped.
* H3's split at g = 2 is likewise evaluated at each lambda. The threshold 2 stays as registered and is not retuned.

**Why this is a strengthening and not a weakening.** Section 6 already promised that "a lambda sweep is reported alongside every value" and that an unregularised g exceeding its ceiling means the classical kernel is under-regularised. This proposal makes that promise the test rather than a footnote to it. It cannot be gamed in the direction of a positive result, because requiring agreement across four lambdas is strictly harder than picking one.

**What the data already suggests, flagged so the sweep is not read as a formality.** At every lambda, on both datasets, g is larger at the registered bandwidth than at the bandwidth inner CV selected. The ordering is robust even where the magnitudes are not. Since the registered bandwidth is where the quantum kernel performed worse, that ordering points the OPPOSITE way to Huang's prediction: g was highest exactly where the quantum kernel did least well. If that survives the full 360 units it is a finding about g, and it is the reason H2 must not be gated behind anything.

**Status.** In force from 25 September 2026. Every g reported in this project from that date carries its lambda, the full sweep, and the count of units excluded at each lambda for breaching the sqrt(n) ceiling.

---

## D6. The registered power analysis measured the wrong pairs

**Date:** 25 September 2026. **Found after H1 was tested, by `scripts/audit.py` run against this project's own results.** This corrects a figure in the registered document rather than changing the design, and it was found by the tool this project built, on the first file that tool was ever pointed at.

**What section 5 says.** A table of minimum detectable effects "from the measured median paired standard deviation in each arm", giving churn matched 250 a paired sd of 0.0241 and an intersection-union MDE of **0.0171**.

**What that sd actually measures.** `scripts/power_analysis.py` line 62: `KERNELS = ("linear", "rbf", "poly")`. It pairs classical kernels against each other. It was written in week 3, when the classical arm was the only arm that existed, so it could not have measured anything else. The figure is the spread of *classical kernel A minus classical kernel B* on the same split.

**What H1 tests.** The paired difference between the best quantum kernel and the best classical kernel. Two classical kernels on one split score similarly, so their differences are tight. A quantum kernel and a classical kernel do not, and on churn the quantum arm is both much worse and much more variable, so the cross-arm differences are far wider.

**The measurement, from two independent pieces of code.** `primary_tests.py` reported **sd 0.0921** for the churn primary comparison on 20 paired seeds. `audit.py`, written three weeks later and pairing every quantum method against every classical method across all 15 configurations, computes a median cross-arm sd of **0.0921**.

Two figures are needed, not one, and the first version of this record mixed them. Section 5's table is an ARM-level quantity: a median across configurations and method pairs. The exclusion bound attached to a primary-cell test is a PRIMARY-CELL quantity. For churn the two coincide at 0.0921 and that coincidence concealed the conflation until fraud, where they differ by a factor of two.

**Arm level, the quantity section 5's table reports. All six arms, measured by `scripts/audit.py --compare`:**

| arm | registered sd → MDE | observed cross-arm sd → MDE | ratio |
| --- | --- | --- | --- |
| churn 250 | 0.0241 → 0.0171 | 0.0921 → **0.0608** | 3.6x |
| churn 100 | 0.0424 → 0.0298 | 0.1521 → **0.1005** | 3.4x |
| churn 50 | 0.0604 → 0.0427 | 0.2071 → **0.1368** | 3.2x |
| fraud 250 | 0.0085 → 0.0059 | 0.0209 → **0.0138** | 2.3x |
| fraud 100 | 0.0136 → 0.0094 | 0.0553 → **0.0365** | 3.9x |
| fraud 50 | 0.0237 → 0.0163 | 0.0864 → **0.0571** | 3.5x |

**Every row of section 5 is wrong, in the same direction, by between 2.3 and 3.9 times, median 3.5.** The first version of this record covered two arms and described fraud as barely affected; both statements are superseded by the table above. The table was not built from a mistaken measurement of one arm. It was built from the wrong quantity throughout, because when it was written the quantum arm did not exist and classical-versus-classical variance was the only thing measurable.

**Primary cell, the quantity an exclusion bound must quote:**

| cell | observed paired sd → MDE |
| --- | --- |
| churn, PCA at 12 qubits | 0.0921 → **0.0608** |
| fraud, SelectKBest at 8 qubits | 0.0095 → **0.0063** |
| churn bandwidth arm, PCA at 12 (D4) | 0.0353 → 0.0233 |

**What this does and does not change.**

* **The churn H1 rejection stands, but by far less margin than the record claimed.** A rejection does not depend on the prior MDE: the observed difference is −0.0798 with a 95% CI of −0.1229 to −0.0367 and Wilcoxon p = 8.2e−05, and the interval excludes zero on the observed data. What changes is the margin. The effect clears the registered MDE of 0.0171 by 4.7x and its true MDE of 0.0608 by **1.31x**. Any phrasing along the lines of "well clear of what the arm was powered for" is withdrawn.
* **The fraud exclusion bound stands, corrected from 0.0059 to 0.0063.** That figure is the primary cell's own paired sd of 0.0095, which is the right quantity for a bound attached to a primary-cell test. The published claim moves by less than the precision floor of D2. The fraud ARM as a whole is a different matter: 0.0138 against a registered 0.0059.
* **Every statement of the form "a null result here would exclude effects larger than X" was wrong**, on both datasets and at all three training sizes, and the corrected figures are in the table above.
* **Section 5's declaration that the churn 50-per-class arm is underpowered becomes far more true.** It was registered as resolving 0.0427 and disqualified from hypothesis testing on that basis. It actually resolves **0.1368**, three times coarser than the figure that already disqualified it.
* **The bandwidth arm's null on churn (D4) excludes effects larger than 0.023, not 0.017.** Its point estimate of −0.0101 and interval of −0.0267 to +0.0064 are unchanged.

**What is NOT done.** Section 5 of the pre-registration is not edited. Version 1.0 stands as registered, error included, and this record is the correction. No test is re-run and no verdict changes.

**Corrections to this record, same day, in the order they were made.** First: the original gave fraud's observed figure as 0.0095 → 0.0063 and called the dataset "barely affected" at 1.1x. That compared an arm-level registered number against a primary-cell observed one. Measured the same way as the registered figure, fraud is 0.0209 → 0.0138, a factor of 2.3. The conflation survived review because churn's two figures are identical to four decimal places by coincidence. Both quantities are now tabulated separately and neither is described as the other. Second: the original covered two arms of six. An audit sweep across all six found every one wrong by between 2.3 and 3.9 times, so this is a table-wide correction and not a two-dataset one.

**What it says about the project.** The registered design was powered on the only data that existed when it was written, which was reasonable, and nobody checked the assumption once the other arm existed. The check that caught it is nine lines long and had been sitting unwritten for a month. That is the argument for the audit protocol in one sentence. That the correction itself then needed correcting, for mixing two units of the same quantity, is the argument for measuring rather than inferring.

---

## D7. How twenty seeds become one g per unit — the aggregation H2 does not specify

**Date:** 29 September 2026. **Made before g has been computed on any unit beyond
the eight-seed diagnostic in week-4 section 9, and before H2 or H3 has been run
at all.** Like D5 this concerns how a REGISTERED hypothesis is tested, so it is
written down and fixed in advance rather than settled while looking at output.

**The gap.** Section 6 defines H2 as a Spearman correlation between `g_λ` and the
observed mean paired difference in normAP "across all 360 units (2 datasets x 3
mappings x 5 qubit counts x 3 training sizes x 4 quantum settings)". A unit so
defined does not include the seed. Each unit contains **20 seeds**, and two
quantities inside it vary by seed:

* **g itself.** Every seed has its own train/test split, so its own Gram
  matrices and its own g.
* **The classical kernel g is measured against.** Section 6 says lambda comes
  from "the classical model actually being compared against, using the C that
  inner-CV selected for that cell". Inner CV selects per seed, and it does not
  always select the same classical family, let alone the same C.

The observed difference is specified — section 6 says "mean paired difference" —
so only g's aggregation is open. Twenty numbers have to become one and the
registration does not say how.

**The rule, fixed here.**

* g is computed **per seed**, on that seed's own training Gram matrices, against
  **that seed's** inner-CV-selected best classical kernel. That is the pairing
  section 6 describes; anything else would compare a quantum kernel against a
  classical model that was not the one it was benchmarked against.
* A unit's g at a given lambda is the **median across its seeds**. The median
  rather than the mean because week-4 section 9 shows g's distribution is
  heavy-tailed at small lambda: a single under-regularised seed returned 57.3
  against a ceiling of 18.71, and a mean would let one such seed carry a unit.
* The **interquartile range across seeds is reported with every unit**, never
  suppressed. A unit whose seeds disagree widely about g is evidence about g.
* D5's ceiling rule applies per seed before aggregation: a seed breaching its
  own sqrt(n) ceiling at a given lambda is excluded at that lambda, the count is
  reported, and a unit with fewer than 10 surviving seeds at a lambda is
  excluded at that lambda and reported as excluded.

**Sensitivity, declared in advance so it cannot become a choice made afterwards.**
H2 and H3 are also computed with the seed as the unit — 7,200 rows rather than
360 — and both results are reported side by side. If they disagree, the reported
finding is that g's relationship to observed performance depends on the level of
aggregation, which is a fact about g and not a defect in the test. **The 360-unit
version as registered is the confirmatory one**; the per-seed version is a
sensitivity check and is labelled as such wherever it appears.

Note that the per-seed version is not independent within a unit, and the
unit-level version is what section 6 registers precisely because of that. This
is the same unit-of-analysis distinction that this project has now got wrong
five times; stating it before the test rather than after is the whole reason
this record exists.

**Seeds used.** All 20 per unit, matching the sweep. No subsetting for compute.
If the full computation proves infeasible the reduction will be recorded here as
a further amendment **before** it is run, with the seed count and the reason.

**What this does not change.** H2's statistic, alpha, two-sidedness and single-
test status; H3's threshold of g = 2 and its Mann-Whitney U; D5's frozen lambda
sweep and its requirement that sign and significance agree across every lambda
at which no unit breaches its ceiling. None of those is touched.

**Why this is a deviation record and not an edit.** Section 6 is not wrong, it
is silent. The pre-registration is never edited -- D6 states that plainly -- so a
silence is filled here, in advance, in the open, where the date is visible and
the choice can be argued with.

---

## D8 — three further silences in H2 and H3, found by writing the test code

**Date:** 29 September 2026
**Status:** In force. Declared before any sweep output existed on disk.
**Affects:** Section 6 (H2, H3), and D7, which fixed the seed aggregation but
not these.

D7 fixed how twenty seeds become one number for g. Writing the code that
actually performs H2 and H3 turned up three more things neither section 6 nor D7
says, each of which changes a reported result. They are recorded here before the
sweep has produced a single row, which is the only reason this record is worth
anything.

### (a) The observed difference must use the same seeds as the g it is paired with

D7 says a unit's g is the median over the seeds that survive the ceiling rule at
that lambda. It does not say which seeds the observed difference is averaged
over. The obvious reading — all twenty — pairs a median computed on one set of
seeds against a mean computed on another. At lambda = 1e-4 that is not a corner
case: g grows as lambda shrinks, so ceiling exclusions cluster there, and a unit
can easily contribute a g from eleven seeds and a difference from twenty.

**Fixed:** the observed difference is the mean over exactly the surviving seeds
that produced the median g, at each lambda separately. The surviving seed count
is written into every unit record so the pairing can be checked afterwards.

### (b) H2 is also computed on units whose difference exceeds the precision floor

D2 sets the precision floor at roughly 1e-3 in AP. Week 4 established that most
of this project's observed differences sit close to it. A rank correlation across
units whose differences are all smaller than the resolution of the comparison
that produced them is a correlation among noise, and it would reject just as
readily as a real one.

**Fixed:** H2 is computed twice at every lambda, once across all surviving units
as registered and once across the subset whose |observed difference| exceeds the
floor. **The confirmatory verdict requires the subset to agree in sign and also
reject.** The count of units above the floor is reported at every lambda whether
or not the subset changes the verdict.

This is a strengthening, not a loosening: it can only turn a SUPPORTED into a NOT
SUPPORTED, never the reverse. That direction is stated here so the choice cannot
later be read as having been made to rescue a result.

### (c) H3's absolute value cannot tell the two directions apart

Section 6 registers H3 on the distribution of |observed difference| above and
below g = 2. A unit where the classical kernel wins by 0.05 and one where the
quantum kernel wins by 0.05 are identical to that test. If the relationship
between g and performance is directional — and H2 as registered assumes it is,
since it uses the signed difference — then H3 as registered is measuring spread
and is capable of returning a significant result driven entirely by units in
which the quantum kernel loses badly.

**Fixed:** H3 runs exactly as registered, on |observed difference|, and that is
the confirmatory result. The signed version runs alongside as a secondary,
**pre-declared here** rather than selected afterwards from whichever of the two
is more favourable. Both p-values are printed in the same table so neither can be
quoted without the other.

### What this does not change

H2's statistic, alpha, two-sidedness and single-test status. H3's threshold of
g = 2, which stays fixed and untuned. D5's frozen lambda sweep, its ceiling rule
and its requirement that the conclusion hold at every breach-free lambda. D7's
median aggregation, IQR reporting, 10-seed minimum, and the per-seed version's
status as a declared sensitivity check rather than a confirmatory one.

### Two things the code refuses to do, which are also declared here

A confidence interval on a Spearman rho is not in section 6, but this project's
own three-condition verdict rule requires an interval that excludes zero. One is
computed by Fisher z transform and labelled as an addition rather than as
registered. rho is clamped to 1 - 1/(2n) before the transform; without the clamp
a perfect correlation gives arctanh(1) = infinity, no interval, and a verdict rule
that reports the strongest possible result as NOT SUPPORTED. A control covers it.

H3 is reported as NOT ESTIMABLE, never as a null result, when the fixed threshold
of g = 2 puts fewer than three units on one side. This is expected to happen at
small lambda, where g grows and every unit may sit above the split. A fixed
threshold that stops partitioning the data has not found no effect; it has
stopped being a test, and saying so is different from reporting p > 0.05.

### Five controls, because eight defects in week 6 were all caught by controls
and none by a test

D, a monotone synthetic table, must give rho exactly +1 and a SUPPORTED verdict.
E, ten seeds at g = 1 and one at 15, must give median 1.0 where the mean gives
2.27 — the specific behaviour D7 chose the median for, checked rather than
assumed. F, a unit with nine survivors, must leave the table and appear in the
excluded list with its breach count. G, three against three with complete
separation, must reproduce U = 9 and two-sided p = 0.1 exactly. H, g uncorrelated
with the difference, must return NOT SUPPORTED on both tests: a stage that finds
a result in noise is worse than one that finds nothing.

---

## D9 — H2 and H3 can only be computed on the arm week 6 showed is confounded

**Date:** 29 September 2026
**Status:** In force. Declared before any sweep output existed on disk.
**Affects:** Section 6 (H2, H3), and how their result may be stated.

This is a larger problem than any of D8's three and it was found the same way,
by reading which files the sweep actually opens rather than by any test.

### The arm H2 runs on

The registered arm's quantum records carry no bandwidth key at all. Their
`params` are `{"embedding": "angle", "reps": 1}` and the kernel default applies,
which is a bandwidth of 1.0. The classical arm in the same comparison tunes its
kernel by inner cross-validation over a full grid. **Week 6 established that this
asymmetry is the largest single effect in the comparison**: when the quantum side
is given the same bandwidth freedom, the exploratory arm selects 0.0625 to 0.25,
eight to sixteen times smaller than the registered 1.0, and the observed
difference moves accordingly.

H2 asks whether g predicts observed advantage. On the registered arm, the
observed advantage is known to be partly a measure of which side was allowed to
tune. **So H2 as registered tests whether g predicts a quantity that this project
has already shown to be confounded.** That is what will be reported, and it will
be reported in those words. A correlation found there is not evidence that g
predicts kernel quality; it is evidence that g predicts a number containing a
known tuning artefact.

### Why the confound cannot simply be removed

The obvious repair is to recompute H2 on the bandwidth-matched arm. That is not
available. The exploratory bandwidth arm covers **one cell per dataset**: churn
at pca with 12 qubits, and fraud at selectk with 8 qubits. Eighty records each,
being four settings by twenty seeds. That is 4 units per dataset and 8 in total,
against an estimability floor of 12 and a registered universe of 360.

**H2 therefore cannot be recomputed on the unconfounded arm, at any lambda.** The
script reports it as NOT ESTIMABLE rather than as a null result, and prints the 8
units with their g, their per-seed selected bandwidth and their observed
difference, labelled descriptive and not to be quoted as a test. If the sign of
the relation there differs from the registered arm's, that is recorded as a
limitation on H2's headline result.

Extending the bandwidth arm to all 60 cells would make H2 answerable on an
unconfounded comparison. It is not being done inside week 7 and no claim is made
that it will be; the cost is the reason the arm was one cell in the first place.
What is declared here is that the limitation is structural and known in advance,
not discovered afterwards in response to whatever the registered arm returns.

### The defect this uncovered

The sweep built every quantum Gram from a hardcoded `bandwidth: 1.0`. For the
registered arm that is correct, because its params carry no bandwidth and the
default is 1.0 — but correct by coincidence rather than by construction, and
flatly wrong for the bandwidth arm, where the selected bandwidth varies by seed.
It now builds from **the record's own `params`**, so the kernel g is computed for
is the kernel the experiment ran, by construction. Control I proves the two paths
are bit-identical where both apply, which is what shows the earlier hardcode had
not already corrupted anything.

`--arm` now selects the arm, each arm writes to its own file, and the arm is part
of both every row and the resume key. Without that, a resumed run against the
other arm would find the (dataset, size, cell, seed) key already present and skip
silently, producing a file that looks complete and holds two arms' g under one
label. That is the filename-collision failure this project already had once,
one level deeper.

### What this does not change

H2's statistic, alpha, two-sidedness and single-test status. H3's threshold of
g = 2. D5's frozen lambda sweep and ceiling rule. D7's median aggregation. D8's
three fixes. The registered arm remains the confirmatory one, because that is
what section 6 registers, and the confound is reported alongside the result
rather than used as grounds to substitute a different arm after the fact.

---

## D5 — correction, 29 September 2026: the ceiling-breach column was wrong in every row

**Date of correction:** 29 September 2026. **Found by reading the record back,
four days after it was published**, not by any test and not by the audit.
**Affects:** D5's lambda table above, and the identical table in
`docs/week-04-report.md` section 9.

**What gave it away.** The fraud entry at lambda = 1e-4 reads **9/8**. Eight
seeds cannot produce nine breaches. An impossible fraction sat in a published
record for four days, in a document whose subject is the auditing of other
people's numbers.

**The cause.** `scripts/classical_limit.py` line 279 read

    br = sum(1 for v in gr + gs if v > ceil)

which pools the g values at the registered bandwidth with those at the selected
bandwidth into one count. With 8 seeds the denominator is **16, not 8**. The
script printed the count bare, with no denominator; the transcription into both
documents supplied "/8" from the seed count. So every sweep row overstates the
breach rate by a factor of two:

| lambda | as published | actual |
| --- | --- | --- |
| 1e-1 | 0 | 0/16 churn, 0/16 fraud |
| 1e-2 | 0 churn, 2/8 fraud | 0/16 churn, **2/16** fraud |
| 1e-3 | 6/8, 8/8 | **6/16**, **8/16** |
| 1e-4 | 7/8, 9/8 | **7/16**, **9/16** |

**A second error in the same column.** The from-C row reads "2/8 churn, 4/8
fraud". Those figures come from a different line of the script, which reports the
two bandwidths separately, and they are the **registered-bandwidth counts only**.
The selected-bandwidth breaches at from-C — 1/8 on churn and 1/8 on fraud — were
dropped in transcription. So the from-C row and the sweep rows use two different
conventions under one column heading, and the from-C row also understates.

**What this does and does not change.** D5's argument is unaffected in substance:
breaches are real at 1e-3 and 1e-4 on both datasets, lambda-from-C is unusable,
and the case for a frozen sweep with a per-lambda ceiling rule stands exactly as
written. What is withdrawn is the **severity**. "6/8 and 8/8 breaching at 1e-3"
reads as most or all of the evidence being unusable; 6/16 and 8/16 is half. Any
statement of this project's breach rates quotes the corrected table.

**What it is an instance of.** Pooling two different kernels' g into a single
count is the unit-of-analysis conflation D6 records, one level down, and D7 says
this project had got that wrong five times. This is the sixth. It is also the
second time a figure has been damaged by hand-transcription out of a log, which
`scripts/audit_sweep.py` exists to prevent for D6's table and did not cover here.

**Fixed at the source.** `classical_limit.py` now reports the two bandwidth
columns separately, each with its own denominator printed. `geometric_tests.py`
had shipped the same defect in its own breach column — a bare count with no
denominator — and now prints `breaches/total` everywhere, including inside
control F. **A count printed without what it is a count of is treated in this
project as a defect, not a formatting choice.**

**What is NOT done.** D5 above is not edited, and neither is week-04-report.md
section 9. Both stand as published with their wrong column, and this is the
correction, which is the same rule D6 set for itself.

---

## D10 — what H2 and H3 returned, and three wrong explanations of it

**Date:** 29 September 2026
**Status:** **POST-HOC.** Every observation below was made *after* the H2/H3
result was on screen. Nothing here changes the verdict recorded above it, and
nothing here may be used to re-derive one.
**Affects:** how D5's decision rule can be read; what a ceiling breach means;
what the confirmatory verdict is and is not.

### 1. The verdict, which stands

H2 and H3 were executed on 29 September 2026 across all 360 registered units,
7,200 per-seed rows, both datasets, 1,800 (cell, seed) combinations in 55.6
minutes. The analysis was committed at `fd2eae0` and `db30825` before the data
existed; the data was committed before either result was read.

**Both hypotheses return NOT ESTABLISHED.** D5 requires the conclusion to hold at
every lambda at which no unit breaches its sqrt(n) ceiling, and **no lambda
column is breach-free**. The registered decision procedure therefore returns no
verdict, in either direction, at any lambda.

The per-lambda figures, for the record:

| lambda | units | breaches | rho | p | 95% CI | H2 | H3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1e-1 | 360 | 4/7200 | +0.1712 | 1.11e-03 | [+0.069, +0.270] | rejects | rejects |
| 1e-2 | 350 | 657/7200 | -0.0245 | 6.48e-01 | [-0.129, +0.081] | no | NOT ESTIMABLE |
| 1e-3 | 90 | 4574/7200 | -0.3814 | 2.09e-04 | [-0.545, -0.189] | rejects | no |
| 1e-4 | 61 | 4972/7200 | -0.2938 | 2.16e-02 | [-0.508, -0.045] | rejects | no |
| from C | 289 | 2893/7200 | -0.0145 | 8.06e-01 | [-0.130, +0.101] | no | rejects on \|d\| only |

D8(b)'s above-floor subset agreed in sign and significance at every lambda except
from-C, where it flipped to +0.0024 on 279 units.

### 2. Four breaches, one seed, and the only complete column

At lambda = 0.1 there are exactly four breaching observations in 7,200. All four
are the same cell and seed -- **churn, n=100, selectk, 4 qubits, seed 7** --
appearing once per quantum setting, with g of 12.72 to 12.94 against a ceiling of
sqrt(140) = 11.83. Its selected classical kernel is poly at C = 1e-04.

That one seed voids the only lambda column in which **all 360 registered units
survive**. Under the strict reading of D5 the confirmatory verdict at lambda =
0.1 is unavailable because of 0.056% of the observations.

**D5's text admits two readings and the code resolved it silently.** "Every
lambda at which no unit breaches its ceiling" can mean every lambda where nothing
had to be excluded, which is what `scripts/geometric_tests.py` implements and
which nothing satisfies; or it can be read as vacuous after exclusions, reducing
the rule to agreement across all five lambdas. **Under the second reading the
conclusion also fails**, because the sign of rho differs: +0.17 at lambda = 0.1
against -0.38 at 1e-3 and -0.29 at 1e-4. Both readings land on the outcome D5
pre-declared for disagreement, that g's relationship to observed performance
depends on the regularisation chosen, which is a result about the metric and not
a failure of the test. The ambiguity was not disambiguated in advance and is
recorded here rather than resolved, because resolving it now would be choosing a
decision rule with the answer in view.

### 3. The two negative figures are not the same kind of estimate as the positive one

lambda = 1e-3 excludes 270 of 360 units and lambda = 1e-4 excludes 299, in both
cases for exceeding the ceiling. The surviving g range is truncated from above,
so those correlations are computed on a restricted range of the predictor. The
only column with a complete, unselected population is lambda = 0.1, where
rho = +0.1712 gives rho^2 of about 0.03: **g accounts for roughly three percent of
the rank variance in observed difference.** As a pre-training screen that is close
to worthless even taken at face value.

### 4. What a ceiling breach actually measures, and three wrong answers

This section exists because the answer took three attempts and the record of the
failures is more useful than the conclusion.

**The algebra.** With A = sqrt(K_C) (K_C + lam I)^-2 sqrt(K_C), A's eigenvalues
are mu/(mu+lam)^2 over K_C's spectrum, maximised at mu = lam where the value is
1/(4 lam). So the classical contribution to g is **capped at 1/(4 lam) for any
kernel whatsoever**, giving g <= sqrt(||K_Q||_inf / (4 lam)), and since the
ceiling is sqrt(n) with K_Q normalised to trace n, a breach requires

    ||K_Q||_inf / n  >  4 lam

more than 40% of the quantum Gram's trace in one eigenvalue at lambda = 0.1, 4%
at 1e-2, 0.4% at 1e-3. Verified across 960 sampled observations: the bound is
violated 0 times and the necessary condition has 0 false negatives at every
lambda.

**Wrong answer one: the classical kernel is near rank-deficient and that drives
g.** Refuted by its own diagnostic. The lambda = 0.1 amplification is 2.491 in
the breaching cell and 2.487 in a non-breaching cell at the same dataset, size,
qubit count and seed. Identical to three decimals, and both at the 2.5 cap. The
breaching cell has the *lower* effective rank, 6 against 10.

**Wrong answer two: ||K_Q|| is larger in the breaching cell.** It is not. For
angle-r1 it is 65.0 there against 72.7 in the contrast, while g is 12.72 against
2.96. What differed was quantum effective rank, 1 to 6 out of 140 against 54 to
137, which suggested that g is largest where the quantum kernel has collapsed.

**Wrong answer three: therefore D5 names the wrong side, and excluding on the
ceiling selects on the arm under test.** This was written and then withdrawn
before it reached this document, on the evidence of a stratified sample of 60
cells (`scripts/sample_ceiling_mechanism.py`, seed 20260929, sampled on design
factors only with g never consulted, 960 observations):

| lambda | breaches | AUC: quantum concentration | AUC: classical factor | AUC: alignment |
| --- | --- | --- | --- | --- |
| 1e-2 | 11 | 0.723 | 0.526 | 0.668 |
| 1e-3 | 127 | **0.394** | **0.815** | 0.681 |
| 1e-4 | 137 | **0.346** | **0.825** | 0.612 |

**At the lambdas where breaches occur in bulk, the classical amplification factor
predicts a breach with AUC 0.82 and quantum concentration is ANTI-predictive.**
The variance decomposition of log g^2 agrees: `var log a_max` rises from 0.16 at
lambda = 0.1 to 8.08 at 1e-4 while `var log ||K_Q||` is fixed at 1.67, and the
correlation with log g^2 moves from ||K_Q|| dominating at lambda = 0.1
(r = +0.54 against +0.17) to the classical factor dominating at 1e-4 (r = +0.64
against -0.11).

**So D5's description is correct and the objection to it is withdrawn.** "A g
above the ceiling means the classical kernel is under-regularised in the g
computation" is right at the lambdas that matter. The warning text in
`src/qbench/kernels/geometric_difference.py` stands. The reason the classical
factor looked inert at lambda = 0.1 is that its cap there is only 2.5 and most
kernels sit against it, leaving little variance; at 1e-4 the cap is 2,500 and
kernels differ enormously in how near they get.

It follows that the exclusion at small lambda selects mainly on the **classical**
kernel's conditioning relative to lambda, not on a property of the quantum arm.
That is what a regularisation safeguard is meant to do, and the claim in section 3
above is a range-restriction problem rather than selection on the outcome.

What survives of the three attempts: the bound holds in 960/960, and its
looseness is the alignment term, with median g/bound from 0.43 to 0.28 and
rho(g/bound, alignment) from +0.773 to +0.885 at p between 6e-49 and 4e-81.

**One further caveat on the falsifier, which was badly designed.** At lambda =
1e-3 and 1e-4 the necessary condition is satisfied by all 240 sampled
observations, so zero false negatives is guaranteed by the test rather than
earned. At 1e-2 the condition holds for 195 of 240, so catching all 11 breaches
carries p of about 0.11 under random assignment. At 1e-1 the sample contained no
breaches at all. The condition is verified as algebra and is **not** corroborated
as an explanation by that count.

### 5. Two pre-declared warnings that fired exactly as written

D8's degenerate-partition clause: at lambda = 1e-2, H3 put 349 units above the
g = 2 split and **1** below, so it is reported NOT ESTIMABLE rather than as a null.
A fixed threshold that stops partitioning the data has stopped being a test.

D7's aggregation check: per-seed rho at lambda = 1e-3 is -0.0233 at p = 0.23
against the unit-level -0.3814 at p = 2.09e-04. Part of that gap is a population
difference rather than aggregation, because the per-seed version retains
surviving seeds from units the unit-level version discarded whole. Both are
reported; the 360-unit version remains the confirmatory one.

### 6. H3's direction, and what it says about the hypothesis being tested

At lambda = 0.1, median |observed difference| is **0.0235 above** the g = 2 split
and **0.0777 below** it, a gap of -0.0542 with CI [-0.1056, -0.0191],
rank-biserial -0.387, p = 7.93e-07, and the signed secondary rejects at
p = 2.17e-06. **High g goes with smaller differences.** The prediction under test
is that a large geometric difference is what permits a large quantum advantage.

At lambda-from-C, the rule section 6 actually registered, rho = -0.0145 at
p = 0.81 with 2,893 of 7,200 observations breaching and D8(b)'s subset flipping
sign. The registered lambda rule yields no relationship in either direction,
which is the case D5 made in advance.

### 7. What this does not change

The verdict in section 1. H2's statistic, alpha, two-sidedness and single-test
status. H3's threshold of g = 2. D5's frozen lambda sweep and ceiling rule, whose
description of what a breach means is confirmed here rather than corrected. D7's
median aggregation and its sensitivity check. D8's three fixes. D9's confound,
which stands over every correlation above: the observed difference comes from the
arm where the quantum side was frozen at bandwidth 1.0 while the classical side
tuned freely.

No breach-tolerance threshold is introduced. D5's rule is recorded as
unsatisfiable under its strict reading and as ambiguous between two readings, and
that is all. Choosing a tolerance now, with the result in view, is the error D5
itself warned against when it refused to pick the lambda that made g behave. If a
future study wants a breach-tolerant rule it registers one before its data
exists.

---

## D11 — the pre-registration was never registered, and said it was for five days

**Date:** 29 September 2026
**Status:** Correction to a **false factual claim about this document's own
provenance**, not to its design. No hypothesis, threshold, decision rule or power
figure is touched.
**Affects:** `docs/pre-registration.md` header and closing line, `README.md`, and
the standing of every record in this file that rests on commit ordering.

### What it said, and for how long

Three statements were live on a public GitHub repository from 24 September to 29
September 2026:

1. Header: **"Version 1.0. Registered 24 September 2026."**
2. Section preamble: "This document **is registered** before any quantum kernel
   has been evaluated on real data."
3. Closing line: **"Registered at OSF. Any version of this document other than
   the registered one is a draft."**

**None of it was true.** There is no OSF registration. There is no OSF
identifier, DOI or external record of any kind anywhere in this repository, and
none was ever created. The document was written, committed at `61f7db9`, pushed,
and never registered anywhere.

Those five days covered five weekly records, ten deviation records, the
publication of `docs/audit-protocol.md`, and contact with three named researchers
about a protocol for auditing other people's methodology.

### How it was allowed to stand

This was not overlooked. It was tracked and then lost.

* **Week 1, section on open items:** "If the paper is going to claim the
  predicted direction was fixed before the results came in, GitHub commit dates
  are weak evidence because they are author-controlled. An OSF registration or a
  published hash is the credible version. **Needs deciding before week 6, not
  after.**"
* **Week 2:** repeated verbatim.
* **Week 3:** "The pre-registration mechanism, OSF or a published hash, is still
  unchosen."
* **Week 4:** "**Hold this until section 15 is resolved**: registering a design
  whose central question has been answered elsewhere would be worse than not
  registering." That hold was correct at the time.
* **Week 5:** "OSF registration, on hold pending that rewrite." The rewrite meant
  is the pre-registration section 1 rewrite. **D6 states the pre-registration is
  never edited, and week 6 records that rewrite being proposed four times by the
  assistant and never actually being required by anything.**

So from week 6 onward the hold rested on a premise that had already been
withdrawn, while the document went on asserting that the registration existed.
The claim was written on 24 September in the expectation that registration would
follow within days, and nothing in the project's own process caught the gap
between the assertion and the act.

### What the timestamp evidence actually is

`61f7db9`, on a public repository, pushed 24 September 2026, unedited since apart
from this correction. **Git commit dates are set by the author and the history can
be rewritten with a force-push.** That is the whole of it.

This matters beyond the pre-registration, and the cost falls on this file. D5, D7,
D8 and D9 each turn on having been written **before** particular data existed, and
D8, D9 and the sweep commits say so explicitly. The evidence for every one of
those orderings is commit sequence in a repository the author controls. That is
weaker than these records have implied, and it is now stated plainly here rather
than left for a reader to notice.

The internal ordering is still not worthless. Some of it is self-witnessing: D8
predicted that H3 would become NOT ESTIMABLE at some lambda because a fixed
threshold would stop partitioning the data, and lambda = 1e-2 then produced 349
units above the split and 1 below. D7 predicted that a mean over seeds would let
one heavy-tailed seed carry a unit, and D10 records the per-seed and unit-level
results diverging exactly where it said they would. A prediction that specific,
written into a file and then matched by output, is hard to construct after the
fact. But "hard to construct" is not "timestamped by a third party," and the
difference is the point of registering in the first place.

### What is NOT done, and why

**No OSF registration is being created now.** An OSF record dated 29 September
2026, attached to a document whose header claimed 24 September, with the study's
results already computed and committed, would be checkable by anyone and would
read as backdating. It would convert an honest absence into an apparent
misrepresentation. The absence is reported instead.

**The design text is unchanged.** D6 established that the pre-registration is
never edited and that errors in it are corrected by records here, so that the
design cannot be retrofitted to results. That rule protects the design. It does
not require a repository to keep asserting a fact that is untrue, and the three
statements corrected above say nothing about hypotheses, thresholds, power or
decision rules. The corrected text states what the old text said and for how
long, so the edit is self-documenting on the page rather than only in this file.

### Open

Whether **Software Heritage** crawled `github.com/jnchowdary/qml-benchmark-lab`
between 24 and 29 September 2026. It archives public repositories and records its
own visit dates, which the author does not control, so a successful visit in that
window would be genuine third-party evidence that the pre-registration existed in
its current form before the H2/H3 results did. To be checked at
`archive.softwareheritage.org`; if a visit exists it is recorded here as an
amendment with the date and snapshot id, and if it does not, a save can be
triggered which timestamps everything from that point forward without pretending
to cover the past.

Whether to seek a registration at all for the remainder of the project, given
that weeks 8 to 12 are writing and hardware runs rather than new confirmatory
tests, is a separate decision and is not taken here.

### Amendment, 29 September 2026, 17:44: Software Heritage has never archived this repository

The open item above is closed, in the unfavourable direction. Queried at

    https://archive.softwareheritage.org/api/1/origin/https://github.com/jnchowdary/qml-benchmark-lab/visits/

the response is **HTTP 404**:

    {
        "exception": "NotFoundExc",
        "reason": "Origin with url https://github.com/jnchowdary/qml-benchmark-lab not found!"
    }

The origin is unknown to Software Heritage. There has been no crawl, so there is
no visit date, no snapshot, and **no third-party timestamp of any kind for this
repository or for anything in it.**

**Consequence, stated plainly.** The ordering evidence for `pre-registration.md`
and for D5, D7, D8 and D9 is commit sequence in a repository the author controls,
and there is no external record against which to check it. No amendment
strengthening those records is available, and none should be claimed. A reader
weighing whether this study's analysis really was fixed before its data has
exactly one thing to weigh: the internal consistency of the records themselves,
including the specific pre-declarations D10 section 5 documents matching their
outcomes.

**What archiving now would and would not do, so the distinction is not blurred
later.** Triggering a Save Code Now creates an immutable third-party copy of the
repository as it stands today. That prevents any **future** rewriting of this
history from passing unnoticed, and from that point the ordering of subsequent
commits is witnessed by someone other than the author.

It provides **essentially no evidence about the pre-registration's date.** The
pre-registration, the g sweep, the H2/H3 result and every deviation record are
all in the repository simultaneously as of today, so an archive taken now cannot
distinguish a document written on 24 September from one written this afternoon
and dated backwards. Nothing retrospective may be claimed from it, and if a
Software Heritage snapshot is later cited anywhere in this project, it is cited
for what it is: the earliest date on which an independent party is known to have
held a copy, which is **after** every result reported here.

The forward-looking value is real and is the reason to do it. Weeks 1, 2 and 3
each asked for an external timestamp and it was never set up. Weeks 8 to 12 are
writing and hardware runs; if the repository is archived at intervals from now,
the ordering of that work is witnessed even though the ordering of weeks 1 to 7
is not.

---

## D12 — the IBM hardware runs are dropped, one week after the timeline called for them

**Date:** 29 September 2026
**Status:** In force. A departure from the registered **timeline**, not from any
hypothesis, endpoint or decision rule. **No registered claim depends on it.**
**Affects:** Section 13 (timeline). Section 7's backend paragraph is unchanged.

### What was registered

Section 13: *"Weeks 4 ... Week 5 ... Week 6: primary tests. **Weeks 7 to 8: IBM
hardware runs on the primary cells.** Week 9: statistics and the exploratory
sweep. Weeks 10 to 12: writing."*

Section 7 is the only other mention: *"Qiskit is used only as a single-setting
cross-check and **as the route to IBM hardware**; framework wall-clock is never
compared across frameworks."*

**That is the whole of it.** No hypothesis, endpoint, decision rule, power
calculation or "what counts as a result" clause refers to hardware anywhere in
the document. H1, H2 and H3 are simulator-based, all three have now been tested,
and their verdicts stand without a hardware run: H1 disadvantage on churn, H1 not
rejected on fraud, H2 and H3 NOT ESTABLISHED.

### What actually happened

Week 7 ended with no hardware runs and **no hardware code**: nothing in
`scripts/` references IBM, Qiskit Runtime or a hardware backend. The IBM Quantum
allocation was recorded as unconfirmed in week 1, again in week 2, and again in
week 3 — *"The IBM Quantum Open Plan allocation is still unconfirmed"* — and was
never checked. Week 1 also noted that IBM changed the Open Plan in March 2026 and
that *"nobody has checked it."*

So this was not deferred by a decision. It was carried as an open item for seven
weeks without being decided in either direction, and is being decided now, **one
week after the registered window for it opened and closed**. Whether it was even
possible is unknown, because the allocation was never verified.

### Why it is dropped rather than attempted

**The comparison it would measure is confounded.** D9 records that the registered
arm fixes the quantum kernels at bandwidth 1.0 while the classical arm tunes
freely, and that week 6 established this asymmetry is the largest single effect
in the whole comparison. Week 6 further showed that when the quantum side is
given the same freedom, the selected kernels are Gaussian kernels reached
expensively. Putting that on noisy hardware measures a known artefact through a
second source of error and would demonstrate that noise makes a losing kernel
lose more.

**Four weeks remain and two are already allocated.** Week 9 is statistics and the
exploratory sweep; weeks 10 to 12 are writing. Building a Qiskit hardware path
from nothing, against an allocation nobody has confirmed, with unknown queue
times, would consume the last clear execution week to produce a result no
registered claim requires.

### What is being given up, stated so it is not glossed

There is one real argument for running it and it is being declined. The audit
protocol in `docs/audit-protocol.md` was exercised in week 6 against a foreign
pipeline's hardware records — Kakavand et al.'s six `ibm_fez` Grams, condition
number 4.5e+05 — and **has never been run against this project's own hardware
records, because there are none.** That is a gap in the protocol's evidence base,
not in the study's, and it is recorded here as forgone rather than as
unimportant.

Nothing here claims a hardware run would have been uninformative. It claims only
that it was not done, why, and that no registered claim rests on it.

### What this does not change

Section 7's backend paragraph stands: all quantum kernels run on
`lightning.qubit`, a test asserts `default.qubit` agreement to 1e-8, and Qiskit
remains a single-setting cross-check. Reported cost stays hardware-equivalent
per D1 — `QuantumGramFactory.evaluations()` reports n(n-1)/2, which is what a
quantum computer would need, and `simulator_executions()` reports the shortcut
separately. **The paper must not claim quantum kernels are cheap on the strength
of something no quantum computer can do**, and dropping the hardware runs makes
that constraint more load-bearing rather than less.

If a hardware run happens in weeks 9 to 12 it is post-result and exploratory in
the same sense as D4, is labelled as such, and no p-value from it enters the
confirmatory family.

### Open

The IBM Quantum Open Plan allocation has never been checked, across seven weeks
and three weekly records that each flagged it. It is being checked now regardless
of this record, because the answer belongs in the project either way: if the
allocation does not exist, that is a fact about what was ever feasible here, and
if it does, the cost of not using it is known rather than assumed. The result is
appended here when it is known.
