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

**Approval.** Drafted and presented in full, with the problem, the proposal, the frozen sweep and the three licensed outcomes, on 25 September 2026. Approved by Nagesh Kumar Jonnalagadda the same day in conversation, after the alternative (keeping the registered lambda-from-C rule) had been shown to return g = 57.3 for a kernel provably equal to an RBF. The approval was given as assent to proceed rather than as a line-by-line review, which is recorded here plainly; if that was not the intent, this record reverts to DRAFT and no week-5 result computed under it stands.

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

### Amendment, 29 September 2026: the allocation was never sufficient, and the number was in every record

The open item above is closed. The IBM Quantum Platform dashboard for this
account (org "Diarka Quantum", region us-east) shows:

* instance `open-instance`, plan **open**, **10m 0s (100%) remain** — ten minutes
  of QPU time per month, which is the Open Plan after the March 2026 change that
  week 1 flagged as unchecked;
* **"Your trial account expires in 1 day"**;
* no workloads ever submitted.

**What the registered run would have cost.** Section 13 asks for hardware runs on
the primary cells. Every quantum record in this project already reports the
hardware-equivalent figure, because D1 required it: `circuit_evaluations` =
113,575 per record, being 61,075 training pairs (n(n-1)/2 at n_train = 350) plus
52,500 test pairs (150 x 350). Across the registered scope — 4 settings, 20
seeds, 2 datasets — that is

    18,172,000 circuit executions

against an allocation of 600 seconds per month. At 1 ms of QPU time per circuit
that is **5 hours, or 30x the monthly budget**; at 5 ms it is 25 hours and 150x;
and at an implausibly optimistic 0.1 ms it is still 3x over. **The registered
timeline allocated two weeks to a run the available hardware could never have
delivered, at any of those rates.**

This was knowable on 17 September from a single page load, which weeks 1, 2 and 3
each said needed doing. It was also knowable from this project's own output: the
number that makes the timeline impossible has been printed in every quantum
record since week 4, in a field that exists specifically so hardware cost would
not be misreported.

**What was feasible, and is being declined.** One (setting, seed) Gram is 113,575
circuits, roughly two minutes at 1 ms, and fits inside the 600 seconds. That
would have given `docs/audit-protocol.md` its own hardware records rather than
the borrowed `ibm_fez` Grams it audited in week 6. It is not taken: no hardware
code exists, the trial lapses tomorrow, and writing a Qiskit Runtime path to a
deadline would produce untested code carrying a single exploratory artefact —
which is the exact failure mode week 8 spent its day repairing elsewhere in this
repository. **The finding is worth more than the artefact would have been**, and
this is the finding.

**What it changes in the record.** D12's reasoning above gave the confound and
the remaining schedule as the grounds for dropping hardware. Both stand, but they
are now secondary: the primary ground is that the registered run was never
possible within the allocation this project had. Any statement that hardware was
"dropped" should say instead that it was **never feasible as registered**, and
that nobody established this for seven weeks despite three weekly records asking.

The gap in the protocol's evidence base named above is unchanged and now
permanent for this project: the audit protocol has been exercised against another
group's hardware records and never against its own.

### Amendment, 29 September 2026: the author's name, and a second edit to the pre-registration

`docs/pre-registration.md` has now been edited twice since it was written on 24
September. D11 records the first. This records the second, because a document
this project describes as frozen does not get edited silently even for something
this small.

**What changed.** The author line read `Author: Nagesh Chowdary, Diarka Quantum
Ltd.` and now reads `Author: Nagesh Kumar Jonnalagadda, Diarka Quantum Ltd.`,
which is the author's name, confirmed by him on 29 September 2026. The same
correction was applied to `README.md`'s maintainer line and to D5's approval
line above.

**Why this is not a deviation.** Nothing about the design, hypotheses,
thresholds, decision rules or power figures is touched. An author's own name is a
factual attribute of the document in the same category as the OSF claim D11
corrected, and leaving a document asserting the wrong one is not a form of
rigour.

**The part worth recording.** Commits in this session and the previous one used
`Nagesh Jonnalagadda` while the documents said `Nagesh Chowdary`. Week 7 section
8 recorded that discrepancy as an error introduced into the git history and
"corrected" the commits to Chowdary from `5390514` onward. **That correction was
itself wrong**: neither spelling was the full name, including the one adopted as
the fix. A discrepancy was noticed, one side was assumed authoritative without
asking, and the assumption was written up as a finding — in a weekly record whose
own section 8 is about claims asserted rather than checked. Week 7 section 8 now
carries that correction.

Commits before `a1e7b57` stand as written, in both spellings. History is not
rewritten here, and the inconsistency in the log is part of the record rather
than something to tidy away.

### Amendment, 29 September 2026: the history was rewritten, and it destroyed the pre-registration's own citation

The two amendments above understate this. They say commit dates are author-set
and that history *can* be rewritten by a force-push. **It was rewritten**, on 25
September 2026 at around 22:22, and the rewrite invalidated the two commit hashes
this pre-registration cites as its anchor.

### What was found, and how

While diffing a 311 MB backup folder before deleting it, the backup's HEAD
commit `b5bf0431` turned out not to exist in the live repository at all --
`git cat-file` could not find the object. The two hashes named in
`pre-registration.md` line 5 were then checked:

    $ git cat-file -t a8bafbb
    fatal: Not a valid object name a8bafbb
    $ git cat-file -t 61f7db9
    fatal: Not a valid object name 61f7db9

Both are absent. The line reading **"both are on `main` and public"** was false
from 25 September until this record, in the same document and the same paragraph
as the OSF claim the first amendment corrects. That is **three false provenance
statements** in a document whose purpose is to establish provenance.

### What the rewrite actually was

Every sha differs between the two histories, including the root commit, while
messages, order, author, author dates and committer dates are all identical to
the second. For a root commit with an identical tree that is only possible if the
message body differs, and it does:

* pre-rewrite root `ef997fa` ends with `Co-Authored-By: Claude Opus 5` and a
  `Claude-Session:` line;
* current root `aada1c3` ends with `Author: Nagesh Jonnalagadda` and
  `Repository:` instead.

**The rewrite stripped the AI co-authorship trailers from every commit in the
history.** Nothing else changed: the root trees are byte-identical, no blob over
200 KB exists in the old history, no credential-shaped path was ever committed,
and `data/raw` was never in version control. The content of this project is
provably unaltered by the rewrite.

So a commit-message edit -- cosmetic in intent -- invalidated every hash in the
project, including the two the pre-registration depends on, and nobody noticed
for four days.

### What the assistant did, which made it worse

Commits from 26 to 29 September carry `Co-Authored-By: Claude Opus 5` again. The
assistant reinstated by default the exact trailers the rewrite had removed,
across roughly thirty commits, without either party noticing. The repository ran
two attribution conventions either side of 25 September and nobody chose that.

Resolved 29 September: **prose only**. The README's AI-use section is the
declaration; no trailers from this point. The 26 to 29 September stretch is left
as it stands and documented rather than rewritten, because rewriting is what
caused this record to be necessary.

### What is preserved, and what is not claimed

The pre-rewrite history survives as the local branch `prerewrite-20260925`, 25
commits, fetched from the backup. Both cited hashes resolve there. It is **not
published**: pushing it would restore to the public repository the trailers the
rewrite deliberately removed. So the pre-registration now cites hashes that exist
on one machine, in a branch recovered by accident from a folder that had been
moved to `_to_delete` the same evening.

**That is the weakest possible form of the claim and it is stated plainly rather
than dressed up.** Combined with the first two amendments -- no external
registration, and no Software Heritage snapshot -- the position is: this
project's ordering evidence rests entirely on an author-controlled history that
has already been rewritten once, whose original form was nearly deleted tonight
and now exists in a single local copy.

### What this does not change

No hypothesis, threshold, decision rule, power figure or result. The content is
provably identical across the rewrite. What changes is what may be claimed about
when things were written, and the honest answer is now: less than D5, D7, D8 and
D9 imply, and the reader should weigh those records accordingly.

**How it was found is the part worth keeping.** Not by any check in this project,
which has an audit protocol, a mutation harness and 426 tests. By a diff run on a
backup folder because deleting 311 MB on an unverified assurance seemed like the
kind of unchecked claim the day had already been about, twice.

---

## D13 — H3 was ungated from H2, and the departure was never declared

**Date of the departure:** 25 September 2026, recorded in the week-4 record.
**Date of this declaration:** 29 September 2026, **after** H3's result was
computed, read and published in the week-7 record and in D10.
**Affects:** Section 9 (the confirmatory set), and what H3's result may be used
for.

### What section 9 registers

> The confirmatory set is exactly three tests: H1 on churn, H1 on fraud, H2. **H3
> is confirmatory but subordinate to H2 and is reported only if H2 is rejected.**

H2 was not rejected. It returned NOT ESTABLISHED at every lambda, because no
lambda column is free of ceiling breaches. Under section 9 as written, **H3's
result should not have been reported at all.**

It was reported in full: five lambda columns in `docs/week-07-report.md` section
2, its own section 3 headed "H3 points away from the hypothesis under test", and
section 6 of D10. Its lambda = 0.1 result was described as the strongest signal
in the data: median |observed difference| 0.0235 above the g = 2 split against
0.0777 below, p = 7.93e-07, with the signed secondary rejecting at 2.17e-06.

### The departure was decided in advance, and never written down

The week-4 record contains it twice, both before any g had been computed across
the 360 units:

> "...it makes H3 the test that matters rather than one gated behind H2."

> "If the project continues as registered: settle D5, compute g across all 360
> units under whatever lambda rule survives with the sweep as the reported
> quantity, and **test H2 and H3 with H3 ungated**."

The reason is stated there too, and it is a good one: on the eight-seed
diagnostic, g was largest where the quantum kernel performed worst, which points
opposite to Huang's prediction and makes H3 the informative test rather than one
conditional on H2 rejecting.

Section 11 requires that any departure be recorded **in this file**, with its
date, its reason, and whether it was made before or after the affected results
were seen. It was recorded in a weekly narrative instead, and no deviation record
was ever opened. Between 25 and 29 September the project ran, reported and
headlined a confirmatory test that its own registration gates shut, with the
gate's removal documented nowhere a reader of `deviations.md` would find it.

### What this costs, stated without softening

**The multiplicity changes.** Section 9's confirmatory set is three tests.
Ungating H3 makes it four unconditionally, and section 9's statement that no
correction is applied across the H1 pair was written for a three-test family with
H3 conditional. No correction has been applied to the four. Since H2 and H3 both
return NOT ESTABLISHED under D5's rule, no positive confirmatory claim currently
rests on this, but the family is not what section 9 describes and the paper must
say so.

**The "decided in advance" defence rests on evidence D11 just weakened.** The
week-4 record is committed, and its commit precedes the sweep. That is the whole
of the evidence that the ungating was not chosen after seeing H3's numbers. D11's
third amendment establishes that this project's history was rewritten on 25
September, that its ordering evidence is author-controlled, and that no external
timestamp exists. So the claim "this departure predates the data" is supported by
exactly the class of evidence this project has just finished documenting as
weak.

**Therefore, two readings, and the reader picks.** A reader who accepts the
commit ordering may read H3's result as confirmatory under a departure declared
late but decided early. A reader who does not should read H3 as **exploratory**,
per section 11's rule for departures made after results are seen, because from
their position the declaration and the result arrived together. This record does
not choose for them, and the paper states both readings.

### What is not done

H3 is not re-gated. Re-imposing the gate now, with the result known, would be
choosing a reporting rule from the answer -- the same error D5 refused when it
declined to pick the lambda that made g behave, and the same one D10 refused when
it declined to set a breach tolerance. The gate's removal stands as decided in
week 4; what changes is that it is finally recorded where section 11 says it
belongs, and labelled with the doubt its late declaration earns.

No number changes. No threshold moves. H3's five lambda columns stand exactly as
computed.

---

## D14 — DRAFT, NOT ADOPTED. The lambda-from-C rule is unsourced and wrong by a factor of n; the orientation of g is settled from source

**Date drafted:** 30 September 2026.
**Status:** **DRAFT. Requires the author's adoption before it takes effect, and
before any recomputed g is read.** Nothing in this record has been acted on. No
number has been recomputed, no file in `src/` or `scripts/` has been changed, and
no verdict has moved.
**Affects:** `lambda_from_svm_C`; the `from_C` column of D5's sweep; what this
project may state about Huang's geometric difference and about Flórez Ablan et
al.'s use of it.

### 1. Why this is a draft and not a deviation in force

The correction below is justified. It is also, in two of its three possible
forms, **capable of turning a NOT ESTABLISHED verdict into a substantive one**,
and it is being written after that verdict is known.

`scripts/geometric_tests.py` line 663 computes
`clean = [c for c in LAM_COLS if report["by_lambda"][c]["breaches"] == 0]`, and
`from_C` is a member of `LAM_COLS`. A monotonicity bound on the existing data
(g is decreasing in lambda, so g(lam_alt) <= g(lam_grid) for any grid lam not
exceeding lam_alt) shows that under lambda = 1/(2C) at least **5,710 of 7,200**
rows in that column become provably breach-free, with 1,158 inconclusive and 332
unbounded. If the recomputed column reaches zero breaches, `clean` becomes
`['from_C']` and H2's and H3's verdicts become whatever that column reports.

So this is the configuration D5 and D10 both refused: a rule change, contemplated
with the current answer in view, that could manufacture a result. **The
difference from those two cases is that this change is compelled by primary
source rather than chosen for convenience. That is a reason to make it, not a
reason to skip the safeguard.** The safeguard is that the rule, the procedure and
the mapping from outcome to verdict are all fixed, committed and pushed before
any recomputed g exists.

### 2. What is now established, from primary source

Retrieved from the arXiv e-print source of Huang et al., *Power of data in
quantum machine learning*, not from a PDF rendering or any model's transcription
of one.

    source archive SHA-256  b510654c662888d0189b22b7a561b50dcbe28e5b53950b38f7860797c5bc17ad
    maintext.tex SHA-256    ceded212c4b0dec2c7b7b641d1b67cf0dde9e44288cd16d92d2c24c5383ec463

**Equation F19, as in the source:**

    g_gen = sqrt( || sqrt(K^1) sqrt(K^2) (K^2 + lambda I)^-2 sqrt(K^2) sqrt(K^1) ||_inf )

The regularised inverse is on `K^2`. The outermost roots are `K^1`.

**Main-text Eq. (5):**

    g(K^1 || K^2) = sqrt( || sqrt(K^2) (K^1)^-1 sqrt(K^2) ||_inf )     with  s_{K^1} <= g(K^1||K^2)^2 s_{K^2}

**These do not contradict each other.** Appendix F asks the reverse operational
question -- given a function represented by kernel 1, what complexity results
when kernel 2 is trained to reproduce it -- and derives
`s_{K^2} <= g_gen^2 s_{K^1}`. Hence at lambda = 0,
`g_gen = sqrt(|| sqrt(K^1) (K^2)^-1 sqrt(K^1) ||) = g(K^2 || K^1)`. It is an
implicit reversal of the ordered comparison between the main text and the
appendix, not an algebraic inconsistency.

**The claim "Huang's appendix contradicts his main text" is withdrawn before it
was ever published.** It was raised in this session on the strength of two model
transcriptions that agreed with each other, and it did not survive the source.
The transcriptions were right about the indices and wrong about what they meant,
which is the failure mode of reading an equation without its surrounding prose.
The paper could have signposted the transition, since the main text directs the
reader to Appendix F as the detailed derivation, but that is a presentation
remark and this project makes no more of it than that.

**Appendix D's training objective, as in the source:**

    min_w [ lambda <w,w> + SUM_{i=1..N} (residual_i)^2 ]

A plain sum, not `(1/N) * SUM`.

**Huang's own lambda procedure**, which is not derived from any SVM's C: search
the declared grid `{1e-5, 1e-4, 1e-3, 1e-2, 0.025, 0.05, 0.1}` and report g_gen
at the largest lambda satisfying the training-error condition on g_tra. **The
source is internally inconsistent on the boundary**: one passage writes
`g_tra <= 0.045` and the numerical-details passage writes `g_tra < 0.045`. Exact
equality is unlikely to bind in floating point, and this record notes the
discrepancy rather than silently choosing a side.

### 3. This project's orientation is correct. No change is required to it

`geometric_difference_regularised(K_classical, K_quantum, lam=...)` computes

    sqrt( || sqrt(K_Q) sqrt(K_C) (K_C + lam I)^-2 sqrt(K_C) sqrt(K_Q) ||_inf )

which is F19 with `K^1 = K_Q` and `K^2 = K_C`, hence `g(K^2 || K^1)` with those
assignments, hence **g(K_C || K_Q)** -- the quantity whose largeness is Huang's
necessary condition for potential quantum advantage. The orientation used
throughout weeks 4 to 8, and every g in `results/audits/g_units.jsonl`, is the
screen it is claimed to be.

Flórez Ablan et al. implement F19 equally faithfully but pass
`geometric_difference(K_train_poly, K_train_quantum, ...)`, i.e. `K^1 = K_C` and
`K^2 = K_Q`, so their computed quantity is **g(K_Q || K_C)**, the reverse
comparison. Both codebases are source-faithful to F19; they differ in argument
order, and only one order gives the advantage screen.

**What may and may not be said about their paper.** That their code computes
g(K_Q‖K_C) is established from their code and Huang's source. That their paper's
*interpretation* is mismatched to it is **[Likely] and not yet citable**: the
quotes suggesting the mismatch -- a figure caption describing g as "how much
better a CK generalizes than a QK", against a results sentence making large
g(K_C, K_Q) the necessary condition for quantum advantage -- come from a
truncated retrieval of their paper, not from source. Under this project's own
rule, no statement about their interpretation appears in any outward-facing text
until their e-print source has been read the same way Huang's was. Their preprint
is arXiv:2503.05602 and the method is now proven.

### 4. The defect in this project

`src/qbench/kernels/geometric_difference.py`:

```python
def lambda_from_svm_C(C: float, n: int) -> float:
    """...An SVM with penalty C corresponds to regularisation strength
    ~1/(2*C*n) in the kernel-ridge sense. ..."""
    return 1.0 / (2.0 * C * n)
```

**That docstring's claim is withdrawn.** It cited nothing, and against Appendix
D's summed objective it is wrong. Normalising the SVC primal
`(1/2)||w||^2 + C * SUM_i loss_i` so the per-sample loss carries coefficient 1
gives `(1/(2C))||w||^2 + SUM_i loss_i`, so the regulariser-to-loss ratio matching
Appendix D is

    lambda = 1/(2C)

with no factor of n. The argument uses only the ratio of the two coefficients, so
it is unaffected by Appendix D using squared residuals where an SVM uses a hinge
loss; **it establishes the regularisation scaling only, and does not claim the two
objectives are otherwise equivalent.**

Every value in the `lambda_from_C` field of `results/audits/g_units.jsonl` is
therefore smaller than the Appendix-D-consistent value by a factor of n_train,
which is 100, 200 or 350 depending on the arm. The field currently spans 1.43e-07
to 7.14e+01 with median 1.43e-03.

**Neither 1/(2C) nor 1/(2Cn) is Huang's procedure.** Huang does not derive lambda
from C at all. This project and Flórez Ablan et al. both substituted a C-derived
lambda for Huang's g_tra grid search, independently, and neither said so.

### 5. Three candidate responses, and what each risks

| | procedure | source status | effect on `clean` |
|---|---|---|---|
| (a) | recompute `from_C` at lambda = 1/(2C) | consistent with Appendix D and with Flórez Ablan et al. | **can flip.** >=5,710/7,200 rows become breach-free |
| (b) | implement Huang's rule: g_tra over the declared grid, largest admissible lambda | **the only option Huang prints** | **can flip.** A new column, breach status unknown |
| (c) | retire the `from_C` column as unsourced | removes an unsourced quantity | **cannot flip.** lambda=0.1 still breaches, `clean` stays empty |

The asymmetry is the point and is stated plainly: **(c) provably preserves the
current verdict and (a) and (b) can overturn it.** A reader is entitled to notice
that the conservative-looking option is also the one that protects the existing
answer, and that choosing it for that reason would be its own form of selecting
on the outcome. Neither direction is safe by default; what makes the choice
defensible is declaring it in advance.

This project's frozen sweep `{1e-1, 1e-2, 1e-3, 1e-4}` is a **subset** of Huang's
declared grid, so (b) requires adding `1e-5`, `0.025` and `0.05` and computing
g_tra, not rebuilding the analysis.

### 6. Recommendation, which is a recommendation and not a decision

**(b) as the primary correction, with (a) reported alongside it as a secondary,
and nothing retired.**

The reasoning, so it can be disagreed with. (b) replaces an unsourced rule with
the one the source prints, which is the only change that removes rather than
relocates the defect. It is also the thing neither other party did: Flórez Ablan
et al. compute `g_tra` and never compare it to anything, and this project did not
compute it at all. For a project whose contribution is an audit protocol, doing
the source's own procedure -- and documenting that two independent groups skipped
it -- is worth more than either C-derived variant. (a) is worth reporting beside
it because it is what makes a number of this project's comparable to a number of
theirs.

**Adopting this is the author's decision, not the assistant's**, because it amends
a pre-registered analysis. What must be true before any recomputed g is read: the
chosen option is written into this file, the verdict implied by each possible
outcome is written down here in advance, and the commit is pushed.

### 7. What this draft does not decide

No hypothesis, threshold, aggregation rule, ceiling rule, or verdict changes.
H2 and H3 remain NOT ESTABLISHED on the record as it stands. The 360-unit frozen
sweep is untouched and its four columns remain valid under the orientation
confirmed in section 3. D5's account of what a ceiling breach measures, and its
three recorded wrong answers, are unaffected.

---

### Amendment to D14, 1 October 2026: the Fraunhofer source is verified, and the claim against their interpretation is withdrawn

D14 section 3 forbade any outward statement about Flórez Ablan et al.'s
interpretation *"until their e-print source has been read the same way Huang's
was"*. That condition is now discharged. Three of the four open items are
settled, one claim of this project's is withdrawn, and what remains is stated
with its evidence class.

**Provenance.** arXiv:2503.05602, raw e-print source, not a PDF rendering or any
model's transcription of one.

    source archive SHA-256  7ce99d754ecca3c97d3203b1a0ea3796156a36e00a6168ebb91d7a6e6172dbc0
    main.tex SHA-256        1903926fe4b5e28a194a67524fc572812d7ce9143b94210db23035f319fde5b8

Retrieved and read by the author. The assistant's own attempt was refused:
`arxiv.org:443` returned a gateway 403 to CONNECT under this session's egress
policy, logged 2026-10-01T22:09:06Z, and the proxy documentation forbids
retrying or rerouting a policy denial. That is recorded because it is the reason
the primary-source read is the author's and not the assistant's.

#### 1. Their equation, from source, lines 209 to 211

```
g(K_1, K_2) = sqrt( || sqrt(K_1) sqrt(K_2) (K_2 + lambda*1)^-2 sqrt(K_2) sqrt(K_1) ||_inf )
```

labelled `eq:geo_diff_reg`, cited to `\cite{Huang.2021}`. The regularised inverse
is on **K_2**; the outermost roots are **K_1**. This is structurally identical to
Huang's F19.

Line 213 assigns the arguments: *"we are usually interested in the case where
$\mathbf{K}_1=\mathbf{K}_{\mathrm{C}}$ and $\mathbf{K}_2=\mathbf{K}_{\mathrm{Q}}$
are classical and quantum kernel matrices with
$\mathrm{tr}(\mathbf{K}_{\mathrm{C}}) = \mathrm{tr}(\mathbf{K}_{\mathrm{Q}}) = N$"*.

**Their code matches their equation**, and their equation matches their prose's
argument assignment. Paper, equation and implementation are mutually consistent.
The suggestion in `docs/florez-ablan-code-check.md` section 7 that their code
might diverge from their cited source was retracted in that document's C3 and is
now additionally refuted from their own source.

#### 2. Their lambda, from source, line 393

> *"For the geometric difference, we used $\lambda = \nicefrac{1}{2C}$ and for the
> Gram matrix diagonalization, we normalized by the number of data points, i.e.
> $\text{eig}(\nicefrac{\mathbf{K}}{N})$."*

with `C=[32.0, 64.0, 128.0, 512.0, 1024.0]`, so their lambda lies in
[4.88e-04, 1.56e-02]. **No g_tra threshold appears anywhere in the source.** This
confirms from their paper, not only from their code, that they substituted a
C-derived lambda for Huang's declared selection procedure, and it stands up the
finding in `florez-ablan-code-check.md` C6 that `g_tra` is computed in their
pipeline and never consulted.

#### 3. WITHDRAWN: that their paper's interpretation is mismatched to its computation

D14 section 3 recorded this as **[Likely]** on the strength of a truncated
retrieval. The source does not support it, and it is withdrawn.

Their operative prose is faithful to Huang's main text. Line 213: *"only if
$g(\mathbf{K}_{\mathrm{C}},\mathbf{K}_{\mathrm{Q}})\propto\sqrt{N}$ holds, the
necessary condition for potential quantum advantage is fulfilled"*. Line 347:
*"Since the median $g$ values of all models are below the size required for
quantum advantage ... we are guaranteed that the classical model provides similar
or better performance"*. Both are Huang's semantics exactly.

The suspicion rested entirely on one clause in the Fig. 2 caption, line 162:
*"the geometrical difference $g(\mathbf{K}_{\mathrm{C}},\mathbf{K}_{\mathrm{Q}})$,
which indicates how much better a CK generalizes than a QK"*. That clause is
inverted relative to their own lines 213 and 347. **It is one imprecise sentence
in a figure caption, contradicted by the paper's precise statements, and a loose
caption is not a methodological error.** This project does not publish it as one.

#### 4. What does follow, and where the fault lies

Huang's F19 satisfies `s_{K^2} <= g_gen^2 s_{K^1}`, so `g_gen = g(K^2 || K^1)` in
Eq. (5)'s ordering. Their Eq. (4) is F19 with `K^1 = K_C` and `K^2 = K_Q`.
**Therefore the quantity they report as g(K_C, K_Q) is Huang's g(K_Q || K_C), and
the sqrt(N) advantage criterion is applied to the reversed ordered comparison.**

**This is recorded as a notation hazard originating in Huang, not as an error by
Flórez Ablan, Roth and Schnabel.** Huang's appendix presents F19 as the
regularised geometric difference without relabelling it as the reversed
comparison, while the main text directs the reader to that appendix for the
detailed derivation. Any reader treating F19 as "the regularised Eq. (5)" and
substituting K_1 = K_C, K_2 = K_Q lands precisely where they landed. Their
reading is the natural reading of an ambiguous source, in a peer-reviewed and
published paper (Quantum Sci. Technol., DOI 10.1088/2058-9565/ade7ad), and this
project says so rather than implying carelessness.

**This project escapes the hazard by argument order, not by insight.**
`geometric_difference_regularised` feeds F19's template with `K^1 = K_Q` and
`K^2 = K_C`, which yields g(K_C || K_Q), the screen. Nothing in the function's
docstring or in any week 4 to 8 record shows that the reversal in Huang's
appendix was identified at the time. The orientation is correct; the reasoning
for it was not written down, and claiming foresight here would be the same
category of error as D13's late declaration.

#### 5. Evidence classes, stated separately as required

- **Exact source statements:** their Eq. (4) index placement; the K_1 = K_C,
  K_2 = K_Q assignment; lambda = 1/(2C); the C grid; the absence of any g_tra
  rule; lines 213 and 347 on the sqrt(N) criterion; the line 162 caption clause.
- **Code behaviour:** `geometric_difference(K_train_poly, K_train_quantum, 1/(2*C_quantum))`,
  faithful to their Eq. (4).
- **Supported inference:** their reported g(K_C, K_Q) equals Huang's
  g(K_Q || K_C).
- **Unresolved, and its provenance stated:** the `s_{K^2} <= g_gen^2 s_{K^1}`
  bound that licenses the inference above was read from Huang's raw LaTeX **by
  the author**, and the assistant has not independently verified it, having been
  blocked from the source by egress policy. It is the strongest evidence class
  available and is treated as established; a reader who wants it checked should
  read Huang's Appendix F directly.

#### 6. Consequence for this project

**A g from this project and a g from theirs are reciprocal-direction quantities
and must never be placed side by side without naming which each computes.** Three
reconciliations are required and getting two right still gives a wrong answer
that looks right: the orientation above; the lambda convention, theirs 1/(2C)
against this project's 1/(2Cn), which D14 section 4 already records as this
project's unsourced defect; and their training-set size, which their line 219
fixes at *"$N=400$ points ... split them into 320 training and 80 test"*, against
this project's three arms.

D14 section 3's prohibition is lifted only to the extent set out here: this
project may state that their reported quantity is the reversed comparison, must
attribute the ambiguity to Huang's appendix, and may not state or imply that
their paper misinterprets its own computation.

#### 7. What this amendment does not change

No hypothesis, threshold, aggregation rule, ceiling rule or verdict. H2 and H3
remain NOT ESTABLISHED. D14 remains a **DRAFT** and no option among (a), (b) and
(c) is adopted by this amendment. No g has been recomputed.

---

### Amendment, 2 October 2026: the rewrite invalidated the provenance of every measurement, not only the two cited hashes

The third amendment above records that the 25 September rewrite destroyed the two
commit hashes `pre-registration.md` cites. That understates it. **Every result
record in this project stores a `git_commit` that does not exist on `main`.**

#### 1. The scope, measured

Section 10 commits that *"every result record stores its git commit"*. Three
distinct hashes appear across all 15,120 records:

| stored `git_commit` | records | files |
| --- | --- | --- |
| `0b796a3` | 7,520 | every quantum run and bandwidth arm |
| `2cf7ec7` | 7,440 | every classical run, matched and unconstrained, including shuffled |
| `0b2aef4` | 160 | the quantum label-shuffled negative control |

All three resolve to `git cat-file -t`, and **none is an ancestor of `main`**:

    $ git merge-base --is-ancestor 0b796a3 main || echo "NOT AN ANCESTOR"
    NOT AN ANCESTOR OF MAIN
    $ git branch --contains 0b796a3
      prerewrite-20260925

Identically for `2cf7ec7` and `0b2aef4`. All three are reachable only from the
local branch recovered from a backup folder that had been moved to `_to_delete`
on the evening of 29 September.

So section 10's reproducibility commitment is satisfied in form and
unverifiable in practice: a reader who clones the public repository can resolve
the provenance of **no measurement this project has made**.

#### 2. The mapping, and exactly how far it goes

The rewrite changed commit messages only, so each pre-rewrite commit has a
counterpart on `main` with a byte-identical tree. Those counterparts exist and
are unique:

| stored hash | tree | counterpart on `main` |
| --- | --- | --- |
| `0b796a3` | `9cd7769c11d7b83b72b78ea5e1760ec076b3aebf` | `17c92c2560dbb115e6572c881d500176711d8a3c` |
| `2cf7ec7` | `ef4cbc75d14cc209f173d0dd081df98856a8f336` | `60d67715f1a5230c1b19ec92acf80aa28a4bf69c` |
| `0b2aef4` | `36490798e8c0e6e86a7315b970cfae85f41b7fed` | `fbbf166405845a6450d600fb4120354a5120afbf` |

**What a reader with only the public repository can check:** that each
counterpart exists and carries the stated tree.

    git rev-parse 17c92c2560dbb115e6572c881d500176711d8a3c^{tree}
    # expect 9cd7769c11d7b83b72b78ea5e1760ec076b3aebf

**What that reader cannot check, and this is stated rather than glossed:** that
the hash stored in the records ever had that tree. `0b796a3` does not exist
publicly, so its tree cannot be computed by anyone outside this machine. **The
mapping reduces what must be taken on the author's word; it does not remove
it.** An earlier draft of this amendment claimed the mapping was verifiable
without trusting the author. That was wrong and is corrected here.

Full public provenance has exactly one route: publishing
`prerewrite-20260925`. D11's third amendment records the reason against it —
pushing it restores to the public repository the AI co-authorship trailers the
rewrite deliberately removed. **That is a genuine trade-off between attribution
hygiene and public traceability of every measurement in the project, and it is
recorded here as an open decision rather than settled in passing.** Until it is
taken, the honest statement in the paper is that result provenance rests on a
tree-identity mapping to public commits, with the pre-rewrite objects held in a
single local copy.

#### 3. An observation, not a finding

The negative-control records carry `0b2aef4` while the runs they are the control
for carry `0b796a3`, and the two have different trees. So the control was
executed from a different tree state than the experiment. That is unremarkable
if the intervening change touched nothing in the measurement path, and it is the
kind of thing a referee asks about. `git log --oneline 0b796a3..0b2aef4` on the
recovered branch answers it. Not run here, and no claim is made either way.

#### 4. What does not change

No record, no measurement, no verdict, no threshold. The 15,120 records are
intact, the data is intact, and the code at each stored commit is recoverable
from the local branch. H1's rejection on churn, H1's null on fraud, H2 and H3's
NOT ESTABLISHED, and every exploratory family stand exactly as computed. What
changes is solely what may be claimed about whether a stranger can trace them.

#### 5. How this was found, which is the part worth keeping

From a housekeeping line in `docs/week-09-report.md` suggesting someone run
`git cat-file -t 0b796a3`, filed among four loose ends. The first answer was
`commit`, which reads as an all-clear and would have closed the item. The check
that mattered was the second one, and the only reason to run it was that D11's
third amendment had already documented this precise trap for different hashes
four days earlier.

**A record of a past failure prevented a present one, and only because it was
written down in enough detail to recognise the shape again.** That is the
argument for `deviations.md` existing, and it is a better argument than any of
the individual records in it.

---

## D15 — the paper's organising contribution changes from the kernel comparison to the audit protocol

**Date the change was decided:** 25 September 2026, recorded in
`docs/week-04-report.md` sections 14 and 15.
**Date of this declaration:** 3 October 2026. **Nine days late.**
**Affects:** section 8 of the pre-registration, and what the paper leads with.
**Does not affect:** any hypothesis, threshold, decision rule, aggregation rule,
ceiling rule, exclusion, verdict or number.

### 1. The failure this record repeats

Section 11 requires any departure to be recorded **in this file**. The turn was
decided on 25 September and written into a weekly narrative instead:

> **The direction question in section 15 was decided on 25 September: the
> project turns toward the audit protocol.** Reasoning in section 14.
> — `docs/week-04-report.md` section 16

**This is the second time.** D13 records the same failure for H3's ungating:
decided in week 4, reasoned well, written into the weekly record, and never
opened as a deviation until 29 September — after the affected result was
published. The lateness cost H3 its unambiguous confirmatory reading.

Twice now a real decision has been documented in the place that reads like a
diary and not in the place a reader checks. The weekly records are where the
reasoning belongs; `deviations.md` is where the fact that a decision was taken
belongs, and the two are not substitutes.

### 2. The reasoning, as recorded on 25 September

Week 4 section 15, headed "Prior art, found late", records that a literature
search was run for the first time in the project on 25 September and found two
papers that materially overlap. Section 14 then states the consequence:

> Note that Flórez-Ablan et al. already compute g against the √N threshold and
> report it staying below the advantage line at every bandwidth, **so H2 is no
> longer an open question in the form it was registered.**

and

> Either way, three things stand independent of the outcome, because neither
> competing paper does them: average precision with an exact chance-level
> correction on imbalanced data, shuffled-label negative controls, and grid
> adequacy adjudicated against a shuffled null rather than argued from edge
> flags.

So the turn was driven by discovering that the registered question had been
answered by a peer-reviewed paper fourteen months earlier, and by Kakavand et
al. having run a substantially larger study on the same axis. It was not driven
by a result.

### 3. The question a referee will ask, answered directly

**Was the audit-protocol framing chosen because the confirmatory result came
back null?**

**No, on the record, and the dates are checkable.** The turn was decided on 25
September. **H2 and H3 were not executed until 29 September**, four days later,
and the paper's registered lead under section 8 is the H2 result. That result
was not known when the direction changed.

**What was known:** H1 had been tested in week 4, so the churn deficit and the
fraud null were in hand. The framing decision was therefore taken with H1 known
and H2 unknown, and this record says so rather than implying the whole
confirmatory set was blind.

**The caveat that applies to every ordering claim in this project.** The
evidence for "25 September precedes 29 September" is an author-controlled commit
history that was itself rewritten on 25 September. D11's third and fourth
amendments establish that no external timestamp exists, that every
pre-registration hash was invalidated, and that every result record stores a
commit absent from `main`. A reader who does not accept this project's own
history as evidence of ordering should read this declaration as what it is: a
claim about dates, supported by the same class of evidence the project has
documented as weak.

### 4. A material update to the turn's stated premise

The reasoning in section 2 above rests partly on Flórez-Ablan et al. having
settled H2. **What this project verified from source on 1 October weakens that
premise**, and leaving it unstated would be presenting a decision's rationale as
stronger than it is.

Their Eq. (4) is Huang's F19, which the fourth amendment to D11 and the
amendment to D14 establish is the **reversed** ordered comparison:
`g_gen = g(K² ‖ K¹)`. They set K¹ = K_C and K² = K_Q, so the quantity they
report as g(K_C, K_Q) and compare against √N is Huang's g(K_Q ‖ K_C). Whether
their √N comparison is therefore the advantage screen they take it for is a
live question, not a settled one.

**That does not reverse the turn.** Kakavand et al.'s 970 experiments stand
untouched, the three things section 14 names as this project's own stand, and a
null H2 on 360 pre-registered units remains worth reporting whatever the prior
art says. But the specific sentence "H2 is no longer an open question in the
form it was registered" is weaker than it looked on 25 September, and the paper
must not repeat it without this qualification.

**It also makes the case for the new framing stronger rather than weaker.** The
check that found it — read the source, compare the printed equation to the
implementation, establish the ordered arguments — is precisely what the protocol
specifies, applied to the paper that prompted the turn.

### 5. What changes

The paper's organising contribution becomes the protocol: checking equation
ordering against source, checking implementation fidelity against a paper's own
claims, establishing what provenance supports, and stating the limits of the
resulting evidence. The churn and fraud comparison becomes the worked example
that produced it.

Section 8's text — *"All four outcomes are publishable and the paper is written
the same way in each case"* — no longer describes the paper. Section 8 is **not
edited**; version 1.0 stands as registered and this record is the correction, as
with D6.

### 6. What does not change, enumerated

No hypothesis. No threshold. No decision rule. No aggregation rule. No ceiling
rule. No exclusion. No power figure. No verdict. No number.

H1 rejects on churn and does not reject on fraud. H2 and H3 return NOT
ESTABLISHED. The negative control is clean on both datasets. The frozen λ sweep,
D5's ceiling rule, D7's median aggregation and D8's conditions are untouched.
Every exploratory family stays exploratory and bears on no confirmatory
hypothesis. Nothing is recomputed by this record.

### 7. What this record does not authorize

**D14 remains a DRAFT.** No option among (a), (b) and (c) is adopted here. Its
declaration and its complete outcome-to-verdict mapping must be committed and
pushed before any recomputed g is examined.

**`prerewrite-20260925` remains unpublished.** The trade-off in D11's fourth
amendment is untouched and undecided.

**Writing background or framing text authorizes neither.** A change in what the
paper is about does not license recomputation, publication of the recovered
branch, or revisiting any frozen analysis.

---

## D14 — DECISION, 4 October 2026: option (a) is adopted, its stated justification is corrected, and (b) is left open

**Decided** 4 October 2026. **Declared** 4 October 2026, same day, in this file.
**Affected results seen?** The *pre-correction* verdict was seen: H2 and H3 have
been NOT ESTABLISHED on the record since 29 September. **No recomputed g has been
examined**, and this record exists to be pushed before one is.

This closes D14's DRAFT status. It changes one field's definition and nothing
else.

### 1. What is decided

**Option (a).** `lambda_from_svm_C(C, n)` becomes `1 / (2 * C)`, dropping the
factor of `n`. `C` continues to come from inner cross-validation, per cell, as
registered. This is the author's decision, taken under D14 section 6's rule that
adopting an option amends a pre-registered analysis and is therefore not the
assistant's call.

### 2. The ground offered for it, and the ground recorded for it

The ground offered was: *the column's stated purpose is to reproduce the fixed-C
reference calculation, and that purpose must determine the choice regardless of
whether recomputation flips `clean`.*

**The principle is adopted in full. The antecedent is false as written, and is
recorded as false here rather than quietly relied on.**

`docs/pre-registration.md` v1.0 line 112 states the column's registered purpose:

> *"λ is not chosen by hand: it is derived from the classical model actually
> being compared against, via `lambda_from_svm_C(C, n) = 1 / (2·C·n)`, using the
> C that inner-CV selected for that cell."*

That purpose is *λ derived from the classical model actually being compared
against*. It is not reproduction of any external reference calculation, and no
such purpose appears anywhere in the registration.

Flórez Ablan et al. use a **fixed** C grid — `[32, 64, 128, 512, 1024]`,
`main.tex` line 393 — giving λ in [4.88e-04, 1.56e-02]. This project takes C from
inner CV per cell. Measured on all 7,200 rows of `results/audits/g_units.jsonl`:
**nine distinct values of `classical_C`, from 1e-4 to 1e+04**, so under (a) λ
takes nine distinct values from **5.00e-05 to 5.00e+03**.

**(a) adopts their formula. It does not reproduce their calculation**, and the two
λ ranges coincide only over a small part of their span. Any outward text claiming
reproduction or direct numerical comparability would be wrong and checkable
against their line 393.

### 3. The selection-dependence objection applies to (a) as well

(b) was set aside as answering *"a different, selection-dependent question."*
Recorded here: **so does (a).** Under (a), λ is a function of an inner-CV
outcome — nine values spanning eight orders of magnitude, each fixed by which C
the tuning picked in that cell.

The difference between (a) and (b) is not *whether* λ depends on a selection but
*which* selection: (a) routes it through the classical arm's chosen C, (b) routes
it through `g_tra` over Huang's declared grid. **(b) is the one the source
prints.** No outward-facing text may describe (a) as selection-independent, as
principled in a way (b) is not, or as Huang's procedure.

### 4. What (a) therefore is, stated so a reader can check it

A correction of a derivation error inside this project's own registered rule, and
nothing more. The registered purpose in section 2 is preserved unchanged; what
changes is that the derivation now matches the only objective Huang prints —
Appendix D's summed form, as set out in D14 section 4 — instead of resting on a
docstring claim that cited nothing and has been withdrawn.

**That ground is independent of the outcome**, which is the only reason it is
usable here. D14 section 5 recorded that (a) can flip `clean` and that choosing
an option for its effect on the verdict, in either direction, is itself selection
on the outcome.

### 5. (b) is not retired, and (c) is rejected

**(b) remains open.** It is neither adopted nor withdrawn, and it stays on the
open-items list as implementing `g_tra` over Huang's declared grid
`{1e-5, 1e-4, 1e-3, 1e-2, 0.025, 0.05, 0.1}` with the largest admissible λ. The
finding it rests on is already established and reportable: **two independent
groups substituted a C-derived λ for Huang's declared selection procedure, and
neither said so.**

**(c) is rejected.** Retiring the column removes an unsourced quantity, but it is
also the only option that provably preserves the existing verdict, and the
correction in section 4 is available without retiring anything.

### 6. The affected column, and what rests on it

`from_C` — one of five entries in `LAM_COLS` (`scripts/geometric_tests.py:354`),
read from its own `g_from_C` field (line 364), with that plumbing pinned by
`mutation_check.py` mutants at lines 88 and 237.

**D5's `clean` is computed over all five columns** (`geometric_tests.py:663`), and
a non-empty `clean` is the precondition for H2 and H3 returning a verdict at all.
This column can therefore change a verdict. That is why this record precedes the
recomputation rather than following it.

**Unaffected:** the frozen sweep's four columns {1e-1, 1e-2, 1e-3, 1e-4}, and
`d_normap`, which is read from the result records and does not depend on λ.

### 7. The recomputation is a new run, not a rescale

`results/kernels/` is empty. g at a new λ cannot be derived from stored Gram
matrices, so **every classical and quantum Gram must be rebuilt**. The output is
a new run under current HEAD and is written to a new path:

    results/audits/g_units_lam2c.jsonl

`results/audits/g_units.jsonl` and `results/audits/h2_h3_report.json` are
**preserved unmodified as historical results** and remain the records cited by
every verdict published before this date. Nothing overwrites them. The new file
carries its own `git_commit`, and that identifier will resolve on `main` —
unlike the three recorded in D11's fourth amendment.

### 8. Integrity gate, which must pass before any value is read

The re-run recomputes all five columns. **Only `from_C` should differ.** If any of
the four frozen columns differs from `g_units.jsonl` at any of the 7,200 rows,
the re-run is **invalid**, nothing is read from it, and the discrepancy is
investigated as a defect in its own right.

This check is free, it is a genuine test of determinism across the sweep, and it
is stated before the run rather than after.

### 9. Outcome-to-verdict mapping, committed in advance

The existing values already bound the outcome, because g is monotone decreasing
in λ (`docs/week-09-opening.md` section 3): of 7,200 rows, **5,710 are proven
breach-free** under (a), **1,158 are inconclusive**, and **332 cannot be
bounded** because λ_alt falls below the grid. So between 0 and 1,490 rows may
still breach, and **the flip is not guaranteed in either direction.**

| | condition | verdict, fixed now |
|---|---|---|
| **O1** | `from_C` breach-free on all 7,200 rows, with non-degenerate within-cell variation in g | `clean` = {`from_C`}. The registered D5 rule yields a verdict on that column. **That verdict is primary for H2 and H3, whatever its sign**, and §1.2, §6.1 and §6.5 of the paper are rewritten to it. |
| **O2** | one or more rows still breach | `clean` stays empty. **H2 and H3 remain NOT ESTABLISHED.** No paper text changes except this record closing and §3.9 gaining a row. |
| **O3** | breach-free, but `rank_correlation` (`src/qbench/stats.py:80`) **refuses** because `g_from_C` is constant across the 360 units — its existing guard, whose message already reads *"this is not a null result"* | Reported as a **measurement**, with the distinct-value count and tie fraction stated. **No verdict is claimed from a rank correlation on a constant.** λ reaching 5.00e+03 against Grams of trace N ≤ 350 compresses g towards zero, so this is a live branch and is pre-committed rather than invoked afterwards. |

**O3 is exact constancy and nothing looser.** Heavy ties short of constancy are
**not** O3: that case follows O1, with the tie fraction and distinct-value count
reported beside the verdict. Written this way so that "the values looked
degenerate" cannot become an exit from an unwelcome O1.

**O1 is the branch that overturns the existing result, and it is pre-committed as
primary.** What the paper flags under O1 is not the verdict's status but its
provenance: that the column's λ definition was corrected after the pre-correction
verdict was known, with the justification in section 4 and this mapping pushed
first.

**What may not happen under any outcome.** Reporting the λ = 0.1 column's rho as
the headline because it is the figure already known. Reinstating NOT ESTABLISHED
under O1 on the ground that it is the conservative reading — D14 section 5 names
that as outcome selection too. Choosing between O1's verdict and the frozen
sweep's after both have been seen. Describing the new run as reproducing the old
one.

### 10. What does not change

No hypothesis. No threshold. No decision rule. No aggregation rule. No ceiling
rule. No exclusion bound. No power figure.

H1 rejects on churn and does not reject on fraud, and the negative control is
clean on both datasets; none of those depends on λ. The frozen sweep's four
columns remain valid under the orientation established in D14 section 3 and its
amendment. D5's account of what a ceiling breach measures, and its three recorded
wrong answers, are unaffected.

### 11. The DRAFT heading at line 1200 is left as written

D14's heading still reads *"DRAFT, NOT ADOPTED"*. It stays. The draft is a
historical object; this record supersedes its status and is the operative one.
Editing that heading would destroy the evidence that the option was declared
after the draft existed and before the run happened, which is the whole content
of the pre-commitment.

### 12. Scope: the function has three production callers, not one

`lambda_from_svm_C` is corrected **globally**, because the rule itself is wrong
and a second, parallel λ rule would be worse than one corrected rule. The
consequences outside the `from_C` column are therefore enumerated here rather
than discovered afterwards.

| caller | what it does with λ | consequence |
|---|---|---|
| `scripts/geometric_tests.py:242` | the `from_C` column of the 360-unit sweep | the subject of this record; re-run per section 7 |
| `scripts/classical_limit.py:168` | the D4 exploratory classical-limit study — writes `lambda`, `g_selected`, `g_registered` | **its stored outputs were computed under the old rule and are not re-run.** They stand as historical exploratory results, and the λ recorded in them is the λ that was used. The figures citing them in `docs/week-04-report.md` and `docs/week-07-report.md` are unchanged and keep that reading. |
| `scripts/run_quick_benchmark.py:87` | a smoke-level benchmark, no reported result | no consequence |

**What is checked and is unaffected.** `scripts/sample_ceiling_mechanism.py` —
the source of D5's classical-factor cap verification and of the amplification
figures 2.491 and 2.487 that refuted the rank-deficiency explanation — does not
call this function at all. It iterates the frozen `LAMBDAS` tuple at line 87.
**D5's cap result is therefore untouched by this change**, and that was
established by reading the script rather than assumed.

**Tests.** `tests/test_geometric_difference.py:168` asserted only that λ is
positive and monotone decreasing in C, both of which hold under 1/(2C), and that
C <= 0 raises. **No test pinned the factor of n**, which is how the withdrawn
rule survived the whole of the registered sweep unexamined. Two tests are added
with this change: one asserting the exact values and that n does not move the
answer, one asserting that a non-positive n still raises.

**The new test has been shown to fail against the old rule.** The mutation was
run by hand — the function reverted to `1.0 / (2.0 * C * n)` in an isolated copy,
the assertions re-run, first assertion killed, and the working file verified
unchanged by hash afterwards. It is **not** in `scripts/mutation_check.py`,
because that harness is hardwired to `tests/test_geometric_tests.py`
(`TESTS`, line 51; `run_test`, line 251) and its coverage check at line 262
enumerates that file alone. Extending the harness to a second test file is an
open item, recorded here rather than left implicit: until it is done, this
mutant's status rests on a manual run and not on the suite.

**A consequence worth stating plainly:** `classical_limit.py`'s stored outputs
cannot be reproduced from current HEAD after this change. That is a new instance
of the binding problem D11 records, created deliberately and declared here. The
alternative — re-running an exploratory D4 study to keep an unsourced λ rule
consistent with itself — buys nothing.

---

### Amendment to D14's decision, 5 October 2026: outcome **O2** obtained, and the verdict does not move

The option-(a) re-run is complete. The outcome is the one the mapping in the
decision record calls **O2**, and the mapping is what fixes the response, not
this paragraph.

**The integrity gate passed first** (`scripts/check_lam2c_rerun.py`, decision
section 8), before any from_C value was read:

    7,200 old rows, 7,200 new rows, 7,200 shared keys
    [PASS] all four frozen columns bit-identical
    [PASS] all 7 lambda-independent fields identical
    [PASS] lambda_from_C == 1/(2C) on every row

**An unplanned result, recorded because it was not predicted.** The four frozen
columns came back **bit-identical** across six days, a separate interpreter
session and a changed λ rule. The gate only required that they not move; that
they match to the last bit is stronger, and it is the first direct evidence in
this project that the sweep is deterministic end to end. It is established for
these 7,200 rows on one machine and says nothing about another machine, another
BLAS or another library build.

**The outcome.**

| | under 1/(2Cn), withdrawn | under 1/(2C), adopted |
|---|---|---|
| from_C ceiling breaches | 2,893 / 7,200 (40.18%) | **979 / 7,200 (13.60%)** |

**The pre-published bound held.** `docs/week-09-opening.md` section 3, written on
1 October from the monotonicity of g in λ and without recomputing anything, said
at least 5,710 rows would be breach-free and at most 1,490 could still breach.
**979 falls inside that interval.** Of the 1,490 rows the bound could not clear,
511 turned out breach-free and 979 did not. A bound published before the run and
satisfied by it is worth more than the breach count itself.

**Not O3.** `g_from_C` takes 7,195 distinct values across 7,200 rows, tie
fraction 0.0007. The column is not degenerate and the O3 branch does not apply.

**Therefore, per O2:** `clean` stays empty, and **H2 and H3 remain NOT
ESTABLISHED.** The λ = 0.1 column retains the four breaching rows recorded in
D5's correction section 2, so **no λ column is breach-free under either λ rule.**
No paper text changes. Sections 1.2, 6.1 and 6.5 stand as written.

**What this does not establish.** It does not establish that the correction was
immaterial. It changed the breach status of **1,914 rows**, two thirds of that
column's breaches. The verdict is unchanged because the registered rule requires
a wholly breach-free column and no column has one, not because the λ rule turned
out not to matter.

**It also does not establish that the verdict is stable.** It now rests on no
column being breach-free under **two** λ rules. Option (b) — `g_tra` over
Huang's declared grid, the only procedure the source prints — remains untried,
and a breach-free column under (b) would reopen H2 and H3. That possibility is
recorded here rather than left for a reader to raise.

**On the shape of this outcome.** O2 is the branch that preserves the existing
result, which is exactly why the mapping had to precede the run. The option, the
justification and the full outcome-to-verdict mapping were committed and pushed
in `67b5c9e` before the sweep started, and the bound in week-09-opening section 3
had already said in public that a flip was possible and not assured. Without
that order, this amendment would be indistinguishable from having picked the
option that protected the answer.

---

### Note, 5 October 2026: two latent defects in this project's own reporting code, and why they are not added to the §5.6 count

Not a deviation. No hypothesis, endpoint, rule, threshold or result moves, and
the pre-registered design is untouched. Recorded because the paper's §5.6
enumerates this project's own failures and a reader is entitled to know the two
below were found, by whom and how.

**Found while making `report_per_setting` and `report_sweep` return their
results instead of only printing them.** Both are in `scripts/primary_tests.py`.

1. The per-setting family's header printed **the literal `4`** as its Holm
   family size. The actual family is the number of settings that produced a
   test, which is `len(labels)` and is never 4 by construction. It was 4 in
   every run ever made, so no printed value was ever wrong.
2. `report_sweep`'s header said **"all cells"** while silently skipping any cell
   with fewer than two paired series. No cell was ever skipped, so no table was
   ever short.

Both are now computed from the data and both report the gap when there is one.

**Neither is added to §5.6's list, and the count there stays at four.** §5.6's
four items are *realised* failures: two where the tool produced wrong answers on
real records, and two where this project's authors asserted something they had
not checked and published it. These two are **latent** — unchecked assertions in
code that would have become wrong answers under inputs that never arrived.
Listing them beside the four would inflate a count the paper uses to argue
against its own contribution, and conflating a defect that fired with one that
did not is the same move §6.1 refuses when it declines to read eight refusals as
eight findings.

**What the two do establish**, and it belongs in §5.6 as a sentence rather than
a list item: **both were found by writing a return value and a test, not by any
check in the audit protocol.** The protocol's own tiers inspect records and
kernels; nothing in it reads this project's reporting code for claims the data
does not support. That is a bounded gap in the instrument, stated plainly.

**What the refactor also establishes, on the persistence question.** The two
families were never lost: all six arms are in `results/analysis/primary_tests.log`,
which is tracked. What that log carries is three rounded values per level at four
decimal places. It carries **no `n`, no median, no sd, no confidence interval and
no sensitivity t-test**, because none of those is printed, and no commit, input
digest or seed list. The earlier description of these families as "stdout-only"
was the assistant's overstatement and is withdrawn here: they were
*captured without provenance and at reduced precision*, which is a different and
smaller problem than not being captured.

**Verification, before the regenerated file was committed.** Stdout is
**byte-identical** across the refactor on all six arms (`diff` of the committed
log against the new run: no output). The regenerated
`results/analysis/primary_tests.json` differs from its predecessor in **zero**
pre-existing fields, compared key by key and recursively. Additions only:
`run` and `quantum_suffix` at top level, and `seeds`, `inputs` and
`exploratory_families` on each result. `inputs` carries the SHA-256 digest of
both record files read, and `run` carries the commit, a UTC timestamp and
`is_new_run: true` with a note that the file authenticates no earlier figure.

**Still not reproducible, and not to be described as such.**
`results/analysis/primary_tests_bw.json`, the exploratory bandwidth arm, was not
regenerated and keeps the old shape with no provenance block. It is a historical
output.

---

### Note, 5 October 2026: an inaccurate commit message of this project's own, recorded rather than rewritten

Not a deviation. No hypothesis, rule, result or document content is affected.
Recorded because this project's case against published work is that a record
must say what happened, and a commit message is a record.

**What the history shows.**

    c9556a4  Paper section 6: discussion
             docs/paper-discussion.md | 156 +++++  (1 file changed, 156 insertions)

    fd86eb2  docs: add paper section 6, discussion
             docs/paper-discussion.md |  30 +--    (18 insertions, 12 deletions)

`c9556a4` created the file. `fd86eb2`, two commits later, **revised** it, and its
subject line says *"add"*. The file already existed and the commit added nothing
new to the repository.

**What `fd86eb2` actually did**, and what its own message body did state
correctly: it narrowed §6.1 and §6.5 from *"g did not predict observed
difference"* to the unusability claim, after a cross-check established that at
λ = 0.1 H2's null **is** rejected (rho = +0.1712, p = 1.11e-03,
CI [+0.069, +0.270]) and that NOT ESTABLISHED is the registered rule declining
to return a verdict rather than a finding of no relationship.

**Provenance of the error.** The message was drafted by the assistant and run by
the author unaltered. It is recorded here with that attribution because the
alternative, leaving it unattributed, is the kind of silence this file exists to
prevent.

**Not corrected in place.** The history is not rewritten. `fd86eb2`'s message
stands as pushed and this note is the correction, by the same rule D11 applies
to the pre-registration: a record that is edited after the fact is weaker
evidence than a wrong record with its correction attached.

**Not added to §5.6's count, and the line that decides it.** §5.6 enumerates
failures of the *protocol*: the tool producing wrong answers on real records, and
the authors making claims about measurements they had not checked. A commit
subject line is neither an instrument output nor a claim about a measurement, and
no number anywhere moved. The boundary is stated explicitly so that it is a rule
rather than a convenience: **an inaccuracy enters §5.6 when it misstates a
measurement or an instrument's behaviour.** By that rule the superseded
exclusion bound printed by `scripts/primary_tests.py` does qualify, and this does
not.

---

### Note, 6 October 2026: the fifth public repair. The confirmatory script printed a superseded exclusion bound for eleven days

Not a deviation from the registered design. D6 already corrected the figure on
**25 September 2026**; what failed is that the correction never reached the code.
The original failure and its correction are preserved above in D6 and are not
edited here.

**What was wrong.** `scripts/primary_tests.py` carried the constant `MDE_IU`
holding section 5's registered table. When a confirmatory arm does not reject,
the script prints *"an advantage larger than X in normAP is excluded at 80%
power in this cell"*. For fraud at 250 per class it printed **0.0059**.

Three records carried that figure:

| where | what it said |
|---|---|
| `scripts/primary_tests.py` line 72 | `("fraud", 250): 0.0059` |
| `results/analysis/primary_tests.log` line 78 | the printed bound, 0.0059 |
| `tests/test_primary_tests.py` line 152 | `assert "0.0059" in out` |

Meanwhile `docs/paper-draft.md`, `docs/paper-design.md`, `docs/paper-discussion.md`
and `scripts/audit_sweep.py` all carried D6's corrected **0.0063**. A reader who
cloned the repository and ran the confirmatory script got a number contradicting
every document in it, with nothing anywhere saying why.

**Why it is the authors' failure and not the tool's.** The script did what it
was written to do. D6 was written, published and then not applied to the one
place that prints the quantity it corrects, and a regression test was left
pinning the superseded value with the comment *"fraud's registered
intersection-union MDE"*. That is the same category as the two items already in
§5.6 under claims made without checking.

**Which quantity, which is the part that is easy to get wrong.** D6 records two
tables. Arm level, which section 5 registered: fraud 250 → 0.0138. Primary-cell
paired, *"the quantity an exclusion bound must quote"*: fraud 250 → **0.0063**.
The printed sentence is a bound at the primary cell, so 0.0063 is the correct
figure and **0.0138 would be the wrong quantity**. Substituting the arm-level
number is precisely the conflation D6's own correction note confesses to having
made once.

**The repair.**

* `MDE_IU` is renamed **`MDE_PRIMARY_CELL`**, because the old name said which
  decision rule the figure belonged to and never which quantity it measured, and
  quantity ambiguity is what D6 is about.
* Its contents become D6's primary-cell figures for the two confirmatory cells
  only: churn 250 → 0.0608, fraud 250 → 0.0063.
* The four non-confirmatory rows are **deleted**. They can never print, since the
  bound is emitted only for a confirmatory arm, and D6 computed no primary-cell
  paired figure for them. Leaving four superseded numbers in the source for arms
  that never read them is storage of known-wrong values for no purpose.
* The test asserts **0.0063** and additionally asserts that 0.0059 does **not**
  appear. **The test follows D6's independently measured table.** It was not
  changed to make the code pass; the code and the test were both wrong against a
  figure measured and published eleven days earlier.

**The latent twin, recorded so it is not presented as a single slip.** Churn 250
carried the registered 0.0171 against D6's 0.0608, wrong by 3.6x. It never
printed, because churn rejects and the bound is emitted only on a
non-rejection. Had a re-run failed to reject, it would have printed. It is
corrected in the same change and counted as latent, by the rule stated in the
note of 5 October.

**Effect on the paper's own count.** §5.6 moves from four public failures to
**five**, split two instrument defects and **three** authorial. §1.3 moves from
*"four times in public, twice ... and twice"* to five, two and three. The
existing fifth item in §5.6, the 26x sampling understatement, is of neither kind
and is relabelled *"a further item"* so the ordinal does not collide.

**How it was found, which is the part §5.6 now states.** By inspection, while
refactoring `report_per_setting` and `report_sweep` for an unrelated reason. **No
check in this protocol found it, and none could have.** Tier 1 reads records and
Tier 2 reads kernels. Nothing reads this project's own reporting code for claims
the data does not support, which is where this defect and the two latent ones of
5 October all lived. That gap is now stated in §5.6 rather than left for a
referee.

**What does not change.** No hypothesis, endpoint, decision rule, aggregation
rule, ceiling rule or verdict. H1 rejects on churn and does not reject on fraud.
The exclusion bound a reader should quote has been 0.0063 since 25 September and
still is; only the code now agrees with it. One line of stdout changes, and the
committed analysis log and JSON are regenerated to match.

---

## D16 — PRE-COMMITMENT, 6 October 2026: option (b), Huang's own λ selection rule, specified before it is computed

**Decided** 6 October 2026. **Declared** 6 October 2026, same day, in this file.
**Affected results seen?** The verdicts under the two λ rules already evaluated
are known: `clean` is empty and H2 and H3 are NOT ESTABLISHED. **Nothing has been
computed under the rule specified below.** This record exists to be committed and
pushed before anything is.

**Status, fixed here and not revisable later.** This is a **prospectively
specified follow-up analysis**. It is not part of the registered confirmatory
design, it cannot become part of it, and no outcome of it may be reported as a
confirmatory result. §3.9 and the paper label it so.

---

### 1. The rule, quoted rather than reconstructed

**Source states** (Appendix F, as recorded in D14 §2 and paper §2.3): report
g_gen at the **largest λ in the declared grid such that the training error
g_tra ≤ 0.045**.

**The grid is frozen exactly, and is Huang's, not this project's:**

    {1e-5, 1e-4, 1e-3, 1e-2, 0.025, 0.05, 0.1}

Seven values. This project's frozen sweep {1e-1, 1e-2, 1e-3, 1e-4} is a subset;
1e-5, 0.025 and 0.05 are new.

**F20, the diagnostic:**

    g_tra = λ · sqrt( || sqrt(K¹) (K² + λI)⁻² sqrt(K¹) ||_∞ )

**The boundary is ambiguous in the source** and is not resolved here. One passage
writes `g_tra ≤ 0.045`, the numerical-details passage writes `g_tra < 0.045`.
**The computation uses `≤`.** The run additionally reports how many rows have
`|g_tra − 0.045| < 1e-9` at any grid λ, which is the only population on which the
two readings could differ. If that count is zero, as expected in floating point,
the ambiguity is immaterial and the record says so with a number rather than an
assumption.

### 2. Orientation, which is not a free choice

F20 carries the **same** K¹ and K² assignment as F19. This project's F19 call is
`geometric_difference_regularised(K_C, K_Q, lam=·)`, which is F19 with
**K¹ = K_Q and K² = K_C** (D14 §3). Therefore

    g_tra = λ · sqrt( || sqrt(K_Q) (K_C + λI)⁻² sqrt(K_Q) ||_∞ )

and the matrix inverted in g_tra is the same `K_C + λI` inverted in g_gen. A
consequence, stated so it is checkable rather than discovered: because Flórez
Ablan et al. use the reverse assignment, **their stored `g_tra_train` is the
reverse of this quantity.** That follows from the orientation finding in §2.2 and
is not an additional claim.

### 3. Normalisation

Both Gram matrices are trace-normalised to `tr(K) = N` before anything else, by
`normalise_kernel`, which is what `geometric_difference_regularised` already does
internally with `normalise=True`. **g_tra is computed on the same normalised
matrices, in the same call path**, so that g_tra and g_gen cannot disagree about
which matrices they describe. No separate normalisation is applied.

### 4. Selection unit

**λ is selected per row**, independently, where a row is one
`(arm, dataset, n_per_class, mapping, n_qubits, setting, seed)` tuple — one
classical Gram against one quantum Gram, which is the object Huang's rule is
about. It is **not** selected per cell, per seed or per column.

**The consequence is stated rather than hidden:** the resulting column is not a
single λ. It is a column of per-row λ chosen by a data-dependent rule, exactly as
`from_C` is, and it is therefore **not** comparable to the frozen columns as a
"λ = x" column. Any outward text describing it as a fixed-λ result would be
wrong.

### 5. Tie-breaking

Grid values are distinct, and the rule takes the **largest** admissible λ, so
ties cannot arise in the selection itself. If two grid λ yield bit-identical
g_tra, the larger λ is still the one selected, by the rule as written.

### 6. Numerical tolerances

* g_tra and g_gen are computed in float64 through the existing module, sharing
  `_matrix_sqrt_psd` and `_spectral_norm_sym`, so neither can differ from the
  other in conditioning behaviour.
* The comparison `g_tra ≤ 0.045` is performed on the raw float64 value. **No
  tolerance band is applied**, and no rounding precedes it.
* For every row, the run stores the selected λ, g_tra at that λ, the margin
  `0.045 − g_tra`, and g_tra at the next larger grid λ, so a reader can see how
  close each selection was to moving.
* The breach test is the one D5's accounting already applies to all five existing
  columns: strict `g > ceiling` against the stored `ceiling`, no tolerance.

### 7. Failure handling

| condition | handling, fixed now |
|---|---|
| no grid λ satisfies `g_tra ≤ 0.045` | the row has **no admissible λ**. It is marked `admissible: false`, **no fallback λ is substituted**, it is excluded from the column, and the count is published. |
| g_tra or g_gen non-finite at any grid λ | row marked `valid: false`, counted, published. |
| a linear-algebra routine raises | same as above; the exception text is stored with the row. |

**A column containing any inadmissible or invalid row is INCOMPLETE**, and an
incomplete column yields no verdict. This is the clause that must not be
softened later: a rule that cannot be satisfied on some rows is a finding about
the rule, not a licence to analyse the rows where it can.

### 8. Eligible rows

All **7,200** rows of the registered arm, the same population as the frozen sweep
and `from_C`. No subsetting, no exclusions beyond §7's. The exploratory bandwidth
arm (D4) is **not** included; it bears on no hypothesis. Units are then formed by
D7's median over surviving seeds and D5's ceiling applies per row, exactly as for
every other column.

### 9. Integrity gate, which must pass before any value is read

The run recomputes the four frozen columns alongside the new one. **If any of
them differs from `results/audits/g_units.jsonl` at any of the 7,200 rows, the
run is invalid and nothing is read from it.** Additionally, for every row whose
selected λ is 0.1, **g_gen must equal the frozen λ = 0.1 column bit-identically**,
since it is the same quantity at the same λ. Output goes to a new path,
`results/audits/g_units_gtra.jsonl`; `g_units.jsonl` and `g_units_lam2c.jsonl` are
preserved unmodified.

### 10. A prediction, published before the computation, that determines the outcome

**g_gen is non-increasing in λ**, and this is a theorem rather than an
observation. In `g_gen² = ‖ sqrt(K¹) M(λ) sqrt(K¹) ‖_∞` with
`M(λ) = sqrt(K²)(K²+λI)⁻² sqrt(K²)`, the eigenvalues of M are `μ/(μ+λ)²` with
derivative `−2μ/(μ+λ)³ < 0`, so `M(λ₁) ⪰ M(λ₂)` whenever `λ₁ ≤ λ₂`; congruence by
`sqrt(K¹)` preserves the Loewner order, and the largest eigenvalue is monotone
under it. The project's test suite pins the same fact empirically in
`test_larger_lambda_gives_smaller_or_equal_g`.

The grid's maximum is **0.1**, so every selected λ satisfies `λ* ≤ 0.1`, so
`g_gen(λ*) ≥ g_gen(0.1)` for every row. The ceiling is independent of λ.
**Therefore every row that breaches at λ = 0.1 breaches under this rule.** The
λ = 0.1 column has **4 breaching rows** (D5 correction §2).

**Hence the column cannot be breach-free, and outcome B1 below is excluded in
advance. The outcome is B2 or B3.**

**If the run returns a breach-free column, the implementation is wrong, not the
proof.** That case is pre-committed as an invalid run: nothing is read from it
and the discrepancy is investigated before anything else.

**What option (b) is still for, given that.** The verdict is not what it
produces. It produces the λ values Huang's own rule selects on this data, g at
those λ, and the answer to whether his rule is even satisfiable here — the
quantity neither this project nor Flórez Ablan et al. computed, and the one the
audit contribution rests on. That is reportable under every outcome.

### 11. Outcome-to-verdict mapping, committed in advance

| | condition | consequence, fixed now |
|---|---|---|
| **B1** | complete, valid, and breach-free | Excluded in advance by §10. Should it nonetheless occur, the run is invalid pending resolution of the contradiction. If it survives that, H2 and H3 are **evaluated** under the registered D5/D7/D8 machinery on this column and the verdict reported as the outcome of a **follow-up analysis**, never as confirmatory. **A breach-free column establishes neither hypothesis**; it only removes the precondition failure, and the verdict is whatever the test returns, including NOT SUPPORTED. |
| **B2** | complete and valid, one or more breaches | **NOT ESTABLISHED stands**, and its scope widens from the two evaluated rules to three. No other paper text changes. |
| **B3** | incomplete or numerically invalid: any inadmissible or non-finite row | **Option (b) is reported as unresolved.** No verdict is drawn from a partial column. The inadmissible and invalid counts are published, and the inability to satisfy Huang's rule on this data is itself the reported finding. |

**What may not happen under any outcome.** Substituting a fallback λ for an
inadmissible row. Extending the grid beyond Huang's seven values. Relaxing
0.045, or applying a tolerance band to it, after seeing how many rows fall near
it. Reporting a subset of rows as though the column were complete. Choosing
between B1's verdict and the frozen sweep's after both are known. Describing the
selected-λ column as a fixed-λ result.

### 12. What this record does not change

No hypothesis, endpoint, decision rule, aggregation rule, ceiling rule, exclusion
bound, power figure or verdict. H1's results, the negative control, the frozen
four columns and the `from_C` column are untouched. H2 and H3 remain NOT
ESTABLISHED under the two λ rules evaluated so far, and that scope is the one the
paper states until this record is resolved.

---

### Amendment to D16, 8 October 2026: the gate's monotonicity check gets a declared tolerance, and a tighter clause beside it

**Declared before the outcome was read.** The gate failed, the failure was
diagnosed, this amendment was written and pushed, and only then was the gate
re-run. Loosening a check after it fails is the pattern D16 exists to prevent, so
the loosening is public and argued rather than applied quietly.

**What failed.** `scripts/check_gtra_run.py` required `g_tra` to be
non-decreasing across Huang's grid on every row, with a strict comparison. It
failed on **64 (row, λ-pair) instances across 16 cells** of 7,200 rows.

**What the violations measure.**

| | |
|---|---|
| worst **relative** decrease | **4.693e-11** |
| worst **absolute** decrease | **2.465e-10** |
| values involved | order 1 to 6 |
| most common λ pair | 1e-5 → 1e-4, 40 of 64 instances |
| **closest any violating value comes to 0.045** | **9.848e-01** |
| violating values within 1e-6 of 0.045 | **0** |

**Diagnosis.** Rounding, not a defect. The monotonicity of `g_tra` in λ is a
theorem in exact arithmetic — `λ²(K_C+λI)⁻²` has eigenvalues `λ²/(μ+λ)²`, rising
in λ, and congruence by `sqrt(K_Q)` preserves the Loewner order. 5e-11 relative
is far above one ulp but is what a solve against an ill-conditioned K_C
accumulates; this project's classical Grams run to condition numbers of 1e+19 to
1e+33, and the violations concentrate at the smallest λ, where `K_C + λI` is
closest to singular. Three quarters of them are at the 1e-5 → 1e-4 step.

**Why it cannot affect any result.** Two independent reasons, and the second is
the decisive one.

1. **The selection never relied on monotonicity.** `select_lambda` computes the
   admissible set and takes `max()` of it directly. It does not scan downward
   assuming a down-set. So the stored selection is the largest admissible λ of
   the stored values whether or not those values are monotone. This was a
   deliberate choice recorded in that function's docstring before the run.
2. **Every violating value is at least 23 times the threshold.** The nearest
   comes to within 0.9848 of 0.045. A perturbation of 1e-10 cannot move a value
   of 1.03 across a threshold of 0.045.

**What the check becomes.** Two clauses replacing one:

* **Loose, on the cosmetic property.** A monotonicity violation fails the run
  only if its relative size exceeds **1e-8**. That is roughly 200 times the
  measured worst case, chosen with stated headroom rather than fitted to the
  data, and the gate now **prints the worst relative violation as a number on
  every run** so it is visible on a pass and not only on a failure.
* **Tight, on the property that matters.** The run fails if **any** value
  involved in a monotonicity violation lies within **1e-6** of 0.045, because
  that is the only circumstance in which rounding could change an admissibility
  decision. This clause is new, it is stricter than anything D16 asked for, and
  it currently passes with a margin of 0.9848.

**Scope.** This amends the gate script, which is this project's own addition.
**D16's own section 9 clauses are untouched**: the four frozen columns still have
to be bit-identical, and a row selecting λ = 0.1 still has to reproduce the
frozen λ = 0.1 value exactly. Section 6's rule that the `g_tra ≤ 0.045`
comparison carries **no** tolerance band is also untouched, and the 1e-6 clause
above is a validity check on the run rather than a band around the threshold.

**One disclosure.** Measuring the distance from the violating values to the
threshold required reading `g_tra` values, and those readings show that the 16
affected cells have no admissible λ at any grid point. That is partial outcome
information, obtained before the gate passed, and it is recorded here rather than
left unsaid. It was unavoidable: whether the wobble could move a selection is
precisely the question the gate raised, and it cannot be answered without the
distance to the threshold. No `g_gen` value, no breach count, no selected-λ
distribution and no outcome was read.

---

### Outcome of D16, 8 October 2026: **B3**, and Huang's rule is unsatisfiable on three quarters of the units

The gate passed before any of this was read, after the tolerance amendment above
was committed and pushed. `results/audits/g_units_gtra.jsonl`, 7,200 rows.

**Gate, all nine checks.** Four frozen columns bit-identical. Seven
λ-independent fields identical. All seven grid λ present on every row.
`selected_lambda` equal to the maximum admissible set recomputed from the stored
`g_tra`. `g_selected` equal to g at that λ. Every row selecting λ = 0.1
reproducing the frozen λ = 0.1 value exactly. **g_gen non-increasing in λ on
every row with a worst rise of 0.000e+00** — exactly monotone, no exceptions.
g_tra monotonicity within the declared 1e-8 tolerance, worst 4.693e-11, nearest
violating value 0.9848 from the threshold against a 1e-6 guard. Every row finite.

**The pre-registered prediction held, 4 of 4.** D16 section 10 derived that every
row breaching at λ = 0.1 must breach under this rule, because g_gen is
non-increasing and the grid tops out at 0.1. All four such rows breach here.

**The source's boundary ambiguity is immaterial, as a measured fact.** Rows with
any grid value within 1e-9 of 0.045: **zero**. The `≤` and `<` readings of
Huang's threshold select identically on this data, so D16's choice of `≤` carries
no consequence. That was an assumption in D16 and is now a number.

---

#### The outcome: B3

| | rows | share |
|---|---|---|
| **inadmissible** — no grid λ satisfies g_tra ≤ 0.045 | **5,507** | **76.5%** |
| admissible | 1,693 | 23.5% |
| of those admissible, g_gen breaches its √N ceiling | 348 | 20.6% of admissible |
| **satisfying both Huang's λ rule and his ceiling** | **1,345** | **18.7%** |

Per D16's mapping, B3 obtains: the column is **incomplete**, no fallback λ was
substituted, and **option (b) is reported as UNRESOLVED**. No verdict is drawn
from a partial column. **H2 and H3 remain NOT ESTABLISHED**, now with three λ
rules evaluated rather than two, and the third did not fail to produce a clean
column so much as fail to produce a column at all.

Selected λ, where one existed: 1e-5 → 351, 1e-4 → 373, 1e-3 → 426, 1e-2 → 484,
0.025 → 43, 0.05 → 7, 0.1 → 9.

#### The finding D16 said would be the finding

**On 81.3% of the units, Huang's own λ-selection rule and his own √N ceiling
cannot both be satisfied.** Either no λ in his declared grid passes
g_tra ≤ 0.045, or the only ones that pass force g_gen above its ceiling. The two
constraints bound λ from opposite sides, which paper §2.3 states from the source;
this measures what that costs on imbalanced business tabular data.

**All 348 breaching admissible rows selected λ ∈ {1e-5, 1e-4}**, the two smallest
grid values. **No row selecting λ ≥ 1e-3 breaches.** So the rows where the g_tra
rule permits only a tiny λ are exactly the rows where the ceiling then fails.

**This is the first measurement of that rule by anyone involved.** Flórez Ablan
et al. compute `g_tra` throughout their pipeline and never compare it to
anything; this project did not compute it at all until now. Neither group ran the
only λ procedure the source prints.

**Inadmissibility is uniform, not concentrated.** Churn 2,805 and fraud 2,702;
sizes 1,921 / 1,871 / 1,715 across 250 / 100 / 50; qubit counts between 1,048 and
1,129 across all five; mappings 1,917 pca, 2,118 selectk, 1,472 randproj. By
(dataset, qubits) the share runs from 68.9% to 80.6% with no cell below two
thirds. It is a structural property of this data against this rule, not an
artefact of one corner of the grid.

#### Mechanism, which is POST-HOC and labelled as such

D16 specified no mechanism analysis. What follows was computed after the outcome
was known and is **exploratory**. It bears on no hypothesis.

Define the elasticity `d log g_tra / d log λ` across the grid span. A value of 1
means g_tra scales linearly with λ; 0 means it ignores λ.

| | median | mean | p90 |
|---|---|---|---|
| inadmissible rows | **0.0433** | 0.0783 | 0.2208 |
| admissible rows | **0.5523** | 0.6004 | 0.8924 |

λ rises by a factor of 10,000 across the grid; g_tra on the inadmissible rows
rises by a median factor of **1.49**. On those rows g_tra is nearly independent
of λ, and sits at a median of 1.343 against a threshold of 0.045 — **29.9 times
above it**, with only 228 of 5,507 within a factor of two of it.

**[Certain]** that the two populations separate on this elasticity.
**[Likely]**, not certain, that the cause is `(K_C + λI)⁻²` being dominated by λ
rather than by K_C's spectrum on those rows, which would make g_tra saturate at a
λ-independent value. The elasticity is that regime's signature, but K_C's
eigenvalues were not measured against λ directly, so the attribution is an
inference and is marked as one.

#### What this does and does not change

**Does not change:** any hypothesis, endpoint, decision rule, aggregation rule,
ceiling rule, exclusion bound, power figure or verdict. H1's results and the
negative control are untouched. The frozen four columns and `from_C` are
untouched — the frozen four were recomputed here and came back bit-identical.

**Does change:** the paper states the scope of NOT ESTABLISHED as three λ rules
evaluated, with the third unresolved because its own precondition fails, and
§3.9 records D16 as computed with outcome B3.

**Still cannot be claimed.** That Huang's rule is unsatisfiable in general. It
was measured on two datasets, one grid, one orientation, with statevector
simulation and this project's classical kernels. A rule can be unsatisfiable
where it was tested and workable elsewhere, and nothing here separates those.

---

### Note, 15 October 2026: a second commit message that misdescribes its contents, and the cause named

Not a deviation. No hypothesis, rule, result or document content is affected.
Recorded because this is the **second** instance of the same failure, and because
the first note of 5 October stated the rule this one follows.

**What happened.** `a8f55a7` carries the message *"docs: track week-09-plan.md,
untracked since 1 October"* and contains **eleven** files:

    .gitignore                              (three figure exceptions)
    docs/florez-ablan-code-check.md         (dropped co-author restored in the title)
    docs/paper-draft.md                     (results duplicate removed)
    docs/paper-references.md                (new)
    docs/paper-results.md                   (figures inline, reversal recorded)
    docs/paper.md                           (regenerated)
    scripts/assemble_paper.py               (References added to SECTIONS)
    results/figures/fig1_h2_lambda.png      (new)
    results/figures/fig2_h1_paired.png      (new)
    results/figures/fig3_churn_exploratory.png (new)
    docs/week-09-plan.md                    (new, and the only one the message describes)

Ten of the eleven were intended for a separate commit whose message set out the
three items: removing the results duplicate, committing the figures with the
reason the earlier exclusion decision was reversed, and adding the references.
That message was never used.

**The cause, which is the part worth recording.** The assistant supplied two
commits in two separate messages while the staging area was shared between them,
and asked the author to scroll back for the first. The author ran the one in
front of him, which committed everything already staged. **Every other commit in
this session put the `git add` and the message in one block**, and this one did
not. The failure is in how the instruction was handed over, not in how it was
followed.

**Not corrected in place.** `a8f55a7` is pushed. Amending it would require a
force-push, and the 25 September history rewrite is the direct cause of every
provenance limitation in §4.7 — trading that for a tidier message is a bad
bargain. The message stands as pushed and this note is the correction, by the
rule the note of 5 October set out: *a record that is edited after the fact is
weaker evidence than a wrong record with its correction attached.*

**Not added to §5.6's count.** By the boundary stated on 5 October, an
inaccuracy enters §5.6 when it misstates a measurement or an instrument's
behaviour. A commit subject line does neither and no number moved. The count
stays at five.

**What the contents of `a8f55a7` actually are** is the list above, and the
reasoning for each of the three items is in `docs/paper-results.md` §4.7, in
`docs/paper-draft.md`, and in `docs/paper-references.md`. Nothing about the
repository's content is wrong; only the message describing how it got there.

---

### Note, 15 October 2026: the repository was private throughout, so "pushed before" never meant "published before"

Not a deviation from the registered design. It changes **no** result. It changes
**what every ordering claim in this project is worth**, and it is the most
consequential thing recorded in this file after D6.

**How it was found.** A Software Heritage save request was submitted on
15 October 2026 (request 2558108). It was accepted and then failed:
`save_task_status: failed`, `visit_status: not_found`, no snapshot identifier.
The loader could not find the origin. An unauthenticated query to
`https://api.github.com/repos/jnchowdary/qml-benchmark-lab` returns **404**. The
author's pushes had always succeeded because the author is authenticated, which
says nothing about anonymous access.

**The window.** Private from the project's start on 17 September 2026 until
15 October 2026, as far as the author knows — roughly four weeks, covering every
commit discussed in this file. **No reader could have checked any claim in this
project during its entire working life.**

#### What this withdraws

**"Committed and pushed before the value was read" does not mean published.**
D14 section 9 required that "the chosen option and the mapping from each outcome
to each verdict be committed and pushed *before* any recomputed value is
examined", and recorded that this is what happened. D16 was "specified in full
and pushed before it was computed". Both are true as stated and **neither was
public**. The remote was readable by one person.

What the increment over a purely local commit actually is: GitHub holds
server-side receipt times for a push, which the author does not directly set.
That is a real difference from a local commit, whose timestamp the author
controls completely. But those times are **not exposed to a reader, not
verifiable by one, and not citable**, so the increment is small and this project
does not claim it as evidence. Every phrasing in this file of the form
*"declared publicly"*, *"published before"* or *"public before the run"* is
**withdrawn and replaced by "committed and pushed to a private remote before"**.

**This compounds D11 rather than standing beside it.** D11 already records that
there is no external registration, no pre-result external timestamp, and a
history rewritten on 25 September. Add that the history was invisible to anyone
else, and the ordering evidence is: an author-controlled history, once rewritten,
on a remote only the author could read, with no external attestation at any
point. **A reader who declines to accept that as evidence of ordering is left
with nothing**, and the honest position is that the pre-commitment discipline
documented here is a discipline the author practised, not a claim a reader can
check.

#### What survives

The pre-commitments were real, in the sense that matters for the work: the
option, the mapping and the proof existed before the computation ran, and the
record shows the author constraining himself rather than choosing afterwards.
That is worth something to the author and to anyone who extends the work. It is
**not** worth what a public timestamp would be worth, and this file previously
implied otherwise.

The format claim in paper §6.3 is unaffected. *"A results file in this format can
be audited by a stranger in seconds"* is a property of the format, demonstrable
from the specification in §5.2 and from the week-6 foreign run, and it does not
depend on this repository's visibility. What was undermined is the
**demonstration**, not the claim: no stranger could obtain the file.

#### What is being done

The author has decided to make the repository public and to retry the archive.
**Neither has happened yet.** At 01:25 on 15 October 2026 the unauthenticated
GitHub API still returned 404, and a second save request (2558127) was submitted
against the still-private origin and will fail as 2558108 did. When the
visibility change is made and a save succeeds, the snapshot identifier is
recorded here and in §4.7, with the standing caveat that **it postdates every
result in this paper** and therefore bounds the gap rather than closing it.

An earlier version of the §4.7 paragraph stated that visibility "was changed on
15 October 2026 and the archive retried". It had not been. That sentence was
written in anticipation of an action that had not occurred, which is the same
error this file records on 5 October and twice since, and it was corrected before
being committed.

Nothing in this note is reported as a defect in the tool or in a measurement, so
**§5.6's count stays at five**, by the boundary set on 5 October. It is a defect
in what this project believed about its own availability, found by a service
that tried to read it and could not.
