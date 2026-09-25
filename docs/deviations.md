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

| arm | registered sd → MDE | observed cross-arm sd → MDE | ratio |
| --- | --- | --- | --- |
| churn 250, primary cell | 0.0241 → 0.0171 | 0.0921 → **0.0608** | 3.6x |
| fraud 250, primary cell | 0.0085 → 0.0059 | 0.0095 → **0.0063** | 1.1x |
| churn 250, bandwidth arm (D4) | — | 0.0353 → 0.0233 | — |

**Why fraud is barely affected.** Both arms there sit at normAP 0.966 with 0.034 of headroom, so quantum-minus-classical differences are as tight as classical-minus-classical ones. The error is specific to arms where the two sides genuinely differ, which is to say the arms where power matters most.

**What this does and does not change.**

* **The churn H1 rejection stands.** A rejection does not depend on the prior MDE: the observed difference is −0.0798 with a 95% CI of −0.1229 to −0.0367 and Wilcoxon p = 8.2e−05. The interval excludes zero on the observed data.
* **The fraud exclusion bound stands, corrected from 0.0059 to 0.0063.** The published claim moves by less than the precision floor of D2.
* **Every churn statement of the form "a null result here would exclude effects larger than X" was wrong** and is corrected: the churn 250 figure is 0.061, not 0.0171. The churn rows for 100 and 50 per class in section 5 are derived the same way and are understated by a similar factor; they are not restated here because no confirmatory test rests on them, and section 5's declaration that the 50-per-class arm is underpowered becomes more true, not less.
* **The bandwidth arm's null on churn (D4) excludes effects larger than 0.023, not 0.017.** Its point estimate of −0.0101 and interval of −0.0267 to +0.0064 are unchanged.

**What is NOT done.** Section 5 of the pre-registration is not edited. Version 1.0 stands as registered, error included, and this record is the correction. No test is re-run and no verdict changes.

**What it says about the project.** The registered design was powered on the only data that existed when it was written, which was reasonable, and nobody checked the assumption once the other arm existed. The check that caught it is nine lines long and had been sitting unwritten for a month. That is the argument for the audit protocol in one sentence.
