# QML Benchmark Lab: Week 4 Record

Written 25 September 2026, **revised the same day** after a literature check that should have happened in week 1.
Sections 6, 7 and 14 are revised; **section 15 is new and is the most important section in this record.**
Covers work done 25 September 2026.
**Revised again the same evening** after P1 and P2 were tested out of sample: sections 8, 10, 11 and 13 updated.
Quantum results produced at commit `0b796a3`. 303 tests passing.
Four deviation records were opened this week: D1 and D2 before any real quantum result existed,
D3 at the moment the primary tests first ran, D4 after the registered sweep was seen.
D5 is drafted and **not in force**; week 5 does not start until it is ruled on.

---

## 1. What week 4 was for, and what it turned into

Week 4's job was to build the quantum kernel path, run the four frozen settings across the matched track, and test H1. All of that happened. The sweep finished, the primary tests ran under the registered rule, and both datasets returned a verdict.

What it turned into was a week about whether those verdicts mean what they appear to mean. The registered comparison gave the classical arm a bandwidth grid spanning five decades and the quantum arm no bandwidth at all, and correcting that changed the churn verdict. Correcting it then raised a second question, which is whether a bandwidth-tuned quantum kernel is still a quantum kernel. The answer, for most of the grid, is no.

The registered H1 result stands exactly as computed. What changed is its scope, and scope is most of what this record is about.

---

## 2. The registered result

The sweep ran all four frozen settings across 15 cells, 20 seeds and three training sizes on both datasets: 7,200 records, 0.56 hours of wall clock against a budgeted 46, the difference being D1. Integrity is clean on all six files: every quantum record was scored on the same test points as the classical record it pairs with, every record ran on `lightning.qubit`, no shuffled record leaked into a real-labels file, and no final model failed to converge.

**Churn, primary cell (PCA at 12 qubits, 250 per class): H1 rejected, favouring the classical kernel.** normAP −0.0798 (95% CI −0.1229 to −0.0367, Wilcoxon p = 8.2e−05); ROC-AUC −0.0292 (95% CI −0.0457 to −0.0128, p = 3.4e−04). Both endpoints reject in the same direction. *The arm's registered MDE of 0.0171 is wrong — see D6, added after this record was first written: it was measured between classical kernels, and the true cross-arm figure is 0.0608. The rejection stands regardless, because its interval excludes zero on the observed data, and the effect clears the corrected figure too.*

**Fraud, primary cell (SelectKBest at 8 qubits): H1 not rejected.** normAP −0.0028 (p = 0.25), ROC-AUC +0.0001 (p = 0.82); the two endpoints do not agree on the sign. An advantage larger than 0.0059 is excluded at 80% power (corrected to 0.0063 by D6; the fraud arm as a whole is 0.0138 against a registered 0.0059), on a problem where both arms sit at normAP 0.966 and only 0.034 of headroom exists above the classical baseline. The bound is tight but the ceiling limits what it is worth, and the paper says so.

The registered rule worked as designed and can be shown doing so: churn at 100 per class has ROC-AUC rejecting at p = 0.027 while normAP does not at p = 0.058, and the intersection-union rule correctly refuses.

---

## 3. A defect in the registered document (D3)

H1 is two-sided, so it has three outcomes. Section 8 of the pre-registration names two of them, *advantage found* and *no advantage found*, and is silent on a rejection favouring the classical kernel, which is what occurred. The decision rule itself was untouched and determined the rejection; what was missing was only the label. It is now *disadvantage found*, reported symmetrically with *advantage found* and never as a null.

The label was added after the sign was known, so the label is post-hoc even though the test that produced it was not. Every statement of the churn result carries a pointer to D3.

---

## 4. The bandwidth defect, and why the registered results pointed at it

The registered grid tunes embedding family, repetitions and C. It does not tune bandwidth: `scale_to_angles` fixes the feature range at [0, π] and nothing varies it. The classical arm tunes RBF gamma over eleven values across five decades.

This is not the search-size asymmetry declared in section 9, which concerns grid point counts and inner-CV optimism. Bandwidth is a shape parameter the quantum arm could not vary at all, and it is the parameter that decides whether a fidelity kernel functions beyond a handful of qubits.

The registered results said so themselves. For the angle family, `reps` is a bandwidth knob in disguise, since two applications of `AngleEmbedding` is one application at twice the angle. So the registered grid searched effective scale factors 1 and 2 and nothing below 1, and the smaller scale won **twelve comparisons out of twelve**, across both datasets, all three training sizes and both embedding families, monotonically, sometimes enormously (`iqp-r2` at −0.3008 on churn).

A one-parameter family, a monotone ordering, and the grid boundary at the better end.

---

## 5. The bandwidth arm (D4), and its result

Bandwidth became a kernel hyperparameter selected by inner CV inside each embedding family, exactly as the classical arm selects gamma. The grid, frozen in D4 before the arm ran, is `(0.0625, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0)`: powers of two bracketing the registered value **on both sides**, so the registered kernel is nested inside rather than replaced and the extension cannot be accused of only going the way that helps. The arm writes to separate `_bw` files; a test asserts bandwidth 1.0 reproduces the registered kernel exactly; `compare_runs.py` confirmed byte-identical output on 20 regenerated registered records, 0.00e+00 on both metrics and decision scores.

Adjudication was fixed in advance and follows section 7: the arm runs on real and on permuted labels, and what decides anything is the gain on real labels *relative to* the gain on noise.

**Churn: D4 outcome one.** Real gain +0.0697, permuted gain +0.0005, excess +0.0692 (95% CI +0.0121 to +0.1264, p = 0.0083). Nineteen of twenty seeds chose a bandwidth below 1.0. The churn H1 rejection collapses: normAP goes from −0.0798 (p 8.2e−05) to −0.0101 (p 0.076), and `iqp-r2` swings from −0.3008 to +0.0114, a move of 0.31.

**Fraud: D4 outcome two.** Real gain +0.0029, permuted +0.0012, excess +0.0018 (CI −0.0149 to +0.0185, p = 0.83). Nothing beyond noise, which is what a problem already at 0.966 should show.

So the registered churn rejection is a result about **fixed-bandwidth** quantum kernels. H1 stands as computed; its scope narrows.

---

## 6. What D4 did not anticipate: the gain is real and uninteresting

> **Read section 15 before this section and the next.** The result below was published, peer reviewed, in July 2025. It was derived here independently and without knowledge of that paper, which is a fact about this pipeline and not a contribution to the field.

D4's outcome one says a real gain means the registered result is about fixed-bandwidth kernels. It does not separate a gain that is real from a gain that is real *and* mechanistically empty. This one is the second.

Thirty-seven of eighty churn records chose the grid floor, 0.0625. For the angle family the small-bandwidth limit of a fidelity kernel is a classical Gaussian kernel, analytically:

    K_ij = ∏_d cos²(b·Δ_d/2),  log K ≈ −(b²/4)·‖x−y‖²,  so K → exp(−γ‖x−y‖²) with γ = (reps·b)²/4

Measured at 12 qubits rather than assumed:

| bandwidth | implied γ | max abs difference from that RBF | Spearman of off-diagonals |
| --- | --- | --- | --- |
| 0.0625 | 9.8e−04 | 3.9e−05 | 1.000000 |
| 0.125 | 3.9e−03 | 5.4e−04 | 0.999997 |
| 0.25 | 1.6e−02 | 5.5e−03 | 0.999977 |
| 0.5 | 6.3e−02 | 2.7e−02 | 0.999642 |
| 1.0 (registered) | 2.5e−01 | 5.1e−02 | 0.980998 |

γ = 9.8e−04 is 1e−3, the bottom of the classical RBF grid searched since week 2. On real data the fitted γ matched the prediction to within 2% (median ratio 1.019) and Spearman against the predicted RBF was 0.999999 on churn and 1.000000 on fraud.

Deviations D2 established that both registered endpoints are rank statistics with a reproducibility floor near 1e−3 in average precision. A kernel that ranks every pair identically to six decimal places is the same kernel for everything this study measures.

---

## 7. The surrogate test, because Spearman cannot settle it

"Measurably further from an RBF" and "does something an RBF cannot do" are different claims, and no Spearman threshold bridges them without someone choosing the threshold. So for every quantum kernel the closest RBF was fitted on training Gram matrices only, with no labels, and run through the identical `tune_and_evaluate` on the identical split.

All 160 fitted γ values on the primary cells fall inside the 1e−3 to 1e2 range the classical arm already searched, so there is no escape via a γ nobody would have tried.

**Bandwidth arm, both datasets: nothing survives.** Every effect is within or near the 1e−3 floor, with intervals spanning zero. The bandwidth-tuned quantum kernels are their RBF surrogates.

**Registered arm, churn: three effects survive all three conditions.** `iqp-r1` beats its own closest RBF by **+0.0852** (CI +0.0645 to +0.1058); `iqp-r2` loses by **−0.0493** (CI −0.0913 to −0.0072); `angle-r2` loses by **−0.0162** (CI −0.0232 to −0.0092). `angle-r1` is +0.0000, identical to its surrogate.

This completes the arc, for IQP as well as angle, on out-of-sample scores rather than kernel-space distance: **this quantum kernel is only genuinely quantum in the regime where it performs badly, and where it performs acceptably it has become a classical kernel.** That sentence is, almost word for word, the conclusion of Flórez-Ablan et al. (2025); see section 15. What is arguably still ours is the per-record fitted surrogate run through the identical pipeline, and the imbalanced-data endpoints it was measured with. `iqp-r1` at bandwidth 1.0 beats its nearest RBF by +0.085 while losing to the best classical kernel by −0.1011. Both are true. Tune its bandwidth and the surrogate gap collapses to +0.0021 with an interval of [−0.0094, +0.0136], which excludes the +0.085 effect entirely.

---

## 8. Replication across cells, and a wrong prediction

The +0.0852 came from one cell on one dataset. Fourteen other cells were already on disk. All 15 were run for `iqp-r1`, `iqp-r2` and `angle-r2`, Holm-corrected across cells within each setting.

**The prediction that failed.** I predicted the effect would track the fitted γ, large positive gaps only where γ is large, on the reasoning that a highly localised RBF is a weak comparator. The single sharpest counterexample: `selectk/12` has the largest γ in the table at 4.74 and a gap of −0.0076. Spearman of gap against γ is +0.697 (p = 3.9e−03), real but weaker than the alternative below, and γ and qubit count are confounded here so 15 points cannot cleanly separate them.

**What the table actually shows for `iqp-r1`:** the gap tracks qubit count. Spearman +0.873, p = 2.2e−05. Means by qubit count: +0.0404 at 12, +0.0142 at 10, −0.0118 at 8, −0.0150 at 6, −0.0261 at 4. The departure of the IQP kernel from its nearest RBF grows with qubit count and changes sign between 8 and 10 qubits.

**`angle-r2` is the larger and cleaner effect, and it is negative.** Six of fifteen cells clear all three conditions after Holm, all negative, and five of the six are every SelectKBest cell: −0.2541, −0.2064, −0.1735, −0.1722, −0.1608 at 4, 6, 8, 10 and 12 qubits. Mean by mapping: SelectKBest −0.1934, PCA −0.0070, random projection −0.0046. Here the mediator is γ, not qubits: Spearman against γ +0.802 (p = 3.3e−04), against qubit count +0.316 (p = 0.25, nothing). SelectKBest cells fit γ near 0.06 while PCA and random-projection cells all fit 1.12, and the doubled-angle kernel is catastrophically worse than the broad RBF that best approximates it.

This is the most replicated effect in the study, and it is quantum structure destroying performance relative to the nearest classical kernel, consistently, across every qubit count, on one mapping family.

Both readings were registered as predictions P1 and P2 in `docs/predictions.md`, with falsification conditions, **before** the runs that could confirm them. They have since been tested.

**P1 held in all three arms.** Cell-level Spearman of the `iqp-r1` gap against qubit count: **+0.961 (p 1.2e−08) on fraud**, the dataset that contributed nothing to the hypothesis, +0.698 (p 3.8e−03) on churn at 100 per class, +0.720 (p 2.5e−03) at 50, with churn 250's +0.873 falling between them. Mean gap positive at 12 qubits and negative at 6 and 4 in every arm. Fraud, registered in advance as the weaker test because of saturation, gave the cleanest ordering of the four while compressing magnitudes to a tenth of churn's: right about the ceiling, wrong about the power.

**The confound was raised after the result and has been rejected.** The gap is quantum minus surrogate, so it could have grown with qubit count because the best-fit RBF becomes more localised and therefore worse, with no quantum content at all. The absolute levels say otherwise: the quantum arm's own normAP rises from 0.8850 to 0.9392 on fraud, 0.3944 to 0.4887 on churn 100 and 0.2807 to 0.3822 on churn 50 across 4 to 12 qubits, while the surrogate rises less (+0.035 on fraud), stays flat (−0.008 on churn 100) or falls (−0.046 on churn 50). Comparator decay is real on churn 50 and accounts for roughly a third of the gap growth there; it accounts for none of it on fraud.

**P2 partially held and its quantitative bound is withdrawn.** γ beats qubit count as the correlate on both churn arms (+0.836 and +0.823, against −0.060 and +0.109), and every cell fitting γ below 0.2 is a SelectKBest cell with a gap beyond −0.13, mean −0.213 and −0.234 against −0.019 and −0.037 elsewhere. But the predicted ±0.03 ceiling for cells above γ 0.2 fails: `pca/6` reaches −0.0455 and −0.0705. On fraud no mapping fits γ below 1.0, so P2's antecedent never fires and the arm is untestable rather than passing.

**What this does and does not establish.** The `iqp-r1` kernel improves faster with qubit count than the nearest RBF can follow, which says it is not a classical kernel in disguise. It says nothing about whether it beats the best classical kernel. It does not: at its strongest cell it exceeds its own surrogate by +0.085 and loses to the tuned polynomial by −0.101.

**A methodological note, declared post-hoc.** Fifteen independent Holm-corrected cell tests is the wrong instrument for a monotone trend. `iqp-r1` shows only 2 of 15 cells surviving Holm while the trend across cells sits at p = 2.2e−05. The trend is the finding and the per-cell test is nearly blind to it. Proposing a trend test now, after seeing the trend, is post-hoc and is labelled as such wherever it appears; it is not a registered analysis and no confirmatory claim rests on it.

---

## 9. The geometric difference is not yet measurable (D5, unresolved)

Section 6 sets λ from the classical model: `lambda_from_svm_C(C, n) = 1/(2·C·n)`. The rule does not survive contact with the data, because inner CV reaches the top of the C grid (1e2 on churn, 1e3 on fraud), giving λ near 1.4e−06, at which g diverges.

| λ | churn g at bw 1.0 | churn g at selected bw | fraud g at 1.0 | fraud g at selected | above the √n ceiling |
| --- | --- | --- | --- | --- | --- |
| from C (registered) | 5.979 | 2.529 | 24.518 | 3.708 | 2/8 churn, 4/8 fraud |
| 1e−1 | 2.470 | 1.922 | 3.802 | 1.471 | 0 |
| 1e−2 | 6.748 | 2.101 | 10.182 | 1.593 | 0 churn, 2/8 fraud |
| 1e−3 | 19.796 | 2.287 | 32.103 | 2.746 | 6/8, 8/8 |
| 1e−4 | 42.954 | 2.366 | 87.554 | 3.334 | 7/8, 9/8 |

The decisive case: churn seed 2 is an angle kernel agreeing with an RBF to 2.3e−04 in Gram RMSE and ranking every pair identically, and its g at λ-from-C is **57.3** against a ceiling of 18.71. The most provably classical kernel in the study carries the largest geometric difference. That is a measurement of λ, not of geometry.

Two things are true regardless of λ. The ordering is stable: g is larger at the registered bandwidth than at the selected one at every λ on both datasets. And the registered bandwidth is where the quantum kernel performed **worse**. If that survives all 360 units, g was highest exactly where the kernel did least well, which points the opposite way to what Huang et al. predict, and it makes H3 the test that matters rather than one gated behind H2.

D5 proposes testing H2 across a frozen λ sweep and requiring sign and significance to agree at every λ where no unit breaches its ceiling. It is strictly harder to pass than any single λ. It is **not in force**, because unlike D1 to D4 it changes how a registered hypothesis is tested, and the person who found the problem should not also be the only one who fixes it.

---

## 10. Errors made and caught this week

Recorded because the count matters more than the average.

1. **A cost model wrong by a factor of 2 to 4.** `benchmark_backends.py` timed only `angle-r1`, the cheapest of four settings; at 12 qubits the four span 1.11 to 5.06 ms per statevector.
2. **A regression command that reads as a failure.** `compare_runs.py` compares complete runs; pointed at a 20-record subset it reported FAIL on 1,180 absent records while showing 0.00e+00 on everything common. The check passed; the tool was the wrong shape for the question.
3. **A blanket verdict from a subset.** `classical_limit.py` computed agreement over the angle family and printed one verdict about "the selected quantum kernel". Five of eight churn seeds were IQP, with Spearman down to 0.895. Now one reading per family, and a test forbids the aggregate.
4. **A suppressed warning that mattered.** `warn_above_ceiling=False` hid exactly the diagnostic that would have flagged the λ problem in section 9 immediately.
5. **A finding declared on noise.** `rbf_surrogate.py` reported "the quantum kernel BEATS its own closest RBF" on a mean of +0.0002 with an interval spanning zero, five times below D2's own precision floor, because the verdict checked only a rank-test p-value and a sign. A verdict now requires the rank test to reject, the interval to exclude zero, and the effect to clear the floor.
6. **A family average of opposite effects.** `iqp-r1` at +0.0852 and `iqp-r2` at −0.0493 were averaged into +0.0180 and reported as no detectable difference, which is true of neither. Non-overlapping intervals now block a family verdict.
7. **A wrong mechanism, section 8.** The γ prediction failed against the qubit-count trend.
8. **Four weeks without a literature check.** The largest error of the week and the only one that cost real time rather than a corrected sentence. See section 15. Everything in sections 4 to 7 was built, measured, documented across two deviation records, and written up before anyone searched for whether the central result was already known. It was, since March 2025.

Items 3, 5 and 6 were caught by reading output. Item 8 was caught by a single web search that took under a minute and should have been week 1, day 1.

9. **An output filename that destroyed two of three results.** `rbf_surrogate.py` named its all-cells output after the arm alone, with no dataset or training size, so three runs in one command overwrote each other and only the `tee` logs survived. Scoring P1 then required transcribing sixty rows out of a log by hand, which is not a method.
10. **A trend statistic on the wrong unit.** `trend_stats` correlated over all 300 records rather than the 15 cells, treating twenty seeds of one configuration as twenty independent observations of a trend across cells. It returned fraud `angle-r2` at rho −0.149 with p = 0.0099 on a column where every gap sat at or below D2's 1e−3 precision floor. The cell-level figures, n = 15, are the ones this record reports; every row-level figure printed before the fix is void.

Items 3, 5, 6, 9 and 10 are tests now, each carrying the real numbers that caught it.

11. **The registered power analysis measured the wrong pairs**, and the correction then mixed two units of the same quantity. Not found by reading output but by `audit.py`, on the first file it was ever pointed at. The churn MDE of 0.0171 came from classical-versus-classical variance; the cross-arm figure is 0.0608, off by 3.6x. Recorded as D6, which then had to be corrected the same day: its fraud row compared an arm-level registered figure against a primary-cell observed one, making the dataset look 1.1x off when at arm level it is 2.3x. The conflation survived because churn's two figures coincide to four decimals. The rejection survives all of it; every churn statement of the form "a null would exclude X" did not.

**The pattern, named because the count is no longer the point.** Items 5, 7 and 10 are the same failure: a p-value reached for before the effect size and before the unit of analysis were checked. It produced a finding on a mean of +0.0002, an explanation fitted to the table that refuted its predecessor, and a trend on 300 non-independent rows. It is the failure most likely to survive into a paper, because each instance looked like a result.

---

## 11. Tests and housekeeping

303 at the end of week 4's machinery, up from 204 at the end of week 3; 341 including the audit protocol begun the same day. New files: `test_primary_tests.py` (18), `test_bandwidth.py` (35), `test_classical_limit.py` (15), `test_rbf_surrogate.py` (21). The load-bearing ones are the registered-path regression tests in `test_bandwidth.py` (if bandwidth 1.0 were not exactly the registered kernel, 7,200 records and the H1 verdict would be void) and the three-condition verdict tests in `test_rbf_surrogate.py`.

New scripts: `primary_tests.py`, `bandwidth_arm.py`, `classical_limit.py`, `rbf_surrogate.py`. `primary_tests.py` detects an exploratory arm from the records rather than from a flag, so it prints EXPLORATORY even when run with default options.

---

## 12. Decisions taken this week

- H1 is tested and reported exactly as registered, with D3's third outcome label.
- The bandwidth arm is exploratory under D4 and no p-value from it is confirmatory.
- The classical arm is not re-tuned. Its grids stay frozen.
- Grid boundary pile-up in the bandwidth arm is **not** a licence to widen again: below 0.0625 the kernel provably converges on an RBF with γ → 0, a region the classical arm already covers analytically and empirically.
- D5 was ruled in force on 25 September, recorded with the manner of its approval stated plainly so it can be reversed.
- **The direction question in section 15 was decided on 25 September: the project turns toward the audit protocol.** Reasoning in section 14.

---

## 13. Still open

- **D5.** Unresolved and blocking week 5.
- **The `iqp-r1` trend.** Registered as P1 after the fact, then held in three arms including an independent dataset, with its confound tested and rejected. Still exploratory, still post-hoc in origin, and still not evidence of advantage: at its strongest cell it beats its nearest RBF by +0.085 and loses to the best classical kernel by −0.101. What it does establish is that this one kernel family is not a classical kernel in disguise, which is the only such result in the study.
- **A stale artefact to delete.** `results/analysis/rbf_surrogate_registered_allcells.json` holds churn 50 data under a name implying it is generic, left by the filename bug in item 9. It is committed and must be removed rather than left to be misread.
- **A non-kernel classical baseline.** Gradient boosting on the same matched subsample, minutes of work, and without it "classical kernel beats quantum kernel" leaves open that both are far below what a practitioner would deploy.
- **Scope.** 350 training points is simulator-feasible scale, not deployed scale. The learning curve makes this cost nothing, since the quantum deficit grows with data, but the claim needs saying.
- **OSF registration.** The DOI still needs to go into the pre-registration and the README. **Hold this until section 15 is resolved**: registering a design whose central question has been answered elsewhere would be worse than not registering.
- **The strategic decision in section 15.** Nothing else on this list matters until it is made.

---

## 14. Week 5, conditional on section 15

Nothing starts until two things are settled: D5, and the question section 15 raises.

If the project continues as registered: settle D5, compute g across all 360 units under whatever λ rule survives with the sweep as the reported quantity, and test H2 and H3 with H3 ungated. Note that Flórez-Ablan et al. already compute g against the √N threshold and report it staying below the advantage line at every bandwidth, so H2 is no longer an open question in the form it was registered.

If the project turns toward the audit protocol, week 5 is engineering rather than measurement, and the pre-registration needs a new section 1 — a larger deviation than anything in D1 to D5.

Either way, three things stand independent of the outcome, because neither competing paper does them: average precision with an exact chance-level correction on imbalanced data, shuffled-label negative controls, and grid adequacy adjudicated against a shuffled null rather than argued from edge flags.

---

## 15. Prior art, found late

**This section records a research-process failure, not a result.** It is placed last because that is where it was discovered, and left unabridged because the week-3 record set the precedent that defects are written down at the length they deserve.

On 25 September, after sections 1 to 14 were written, a literature search was run for the first time in the project. Two papers materially overlap.

### Flórez-Ablan, Roth and Schnabel (2025)

"On the similarity of bandwidth-tuned quantum kernels and classical kernels", Fraunhofer IPA. Preprint arXiv:2503.05602, March 2025; published in *Quantum Science and Technology*, DOI 10.1088/2058-9565/ade7ad, 28 July 2025.

Their conclusion is that bandwidth tuning cures exponential concentration only by shrinking effective expressivity until the quantum kernel becomes a classical one: an RBF kernel, or at the small optimal bandwidths actually selected, a low-order Taylor approximation of one. They cover fidelity and projected quantum kernels across five encodings including angle and IQP, they compute Huang's geometric difference against the √N threshold and report it staying below the advantage line at every bandwidth, and they compare out-of-sample ROC-AUC against classical kernels with each at its own optimal bandwidth.

That is sections 5, 6 and 7 of this record, fourteen months earlier, peer reviewed. They also attribute the analytic small-bandwidth RBF limit to earlier work rather than claiming it, so the γ = (reps·b)²/4 derivation in section 6 is a Taylor step off a result that was already second-hand when they cited it.

Their study uses plasticc, kMNIST and a synthetic hidden-manifold dataset at N = 400 with six seeds. No imbalanced business data, no average precision, no chance-level correction, no negative controls, no pre-registration.

### Kakavand, Strohmeyer and Schlotter (2026)

"Benchmarking Quantum Kernel Support Vector Machines Against Classical Baselines on Tabular Data: A Rigorous Empirical Study with Hardware Validation", arXiv:2604.18837, 20 April 2026. Code and data at Zenodo 10.5281/zenodo.19197916.

970 experiments: nine UCI and OpenML binary datasets, four feature maps, three backends including real hardware on ibm_fez, nested CV, Wilcoxon across 29 pairwise comparisons, Kruskal-Wallis factorial analysis, learning curves, seed sensitivity over 8,400 fits, and trainable kernels via kernel-target alignment. Zero of 29 comparisons significant at α = 0.05.

This is a substantially larger study than ours on the axis we chose to compete on. It is also missing, on the evidence available, every check this project built: no bandwidth tuning at all (features enter the circuits without rescaling to a fixed range), no geometric difference, no fitted classical surrogate, no shuffled-label controls, no chance-corrected metric on datasets reaching 75/25 imbalance, and no multiplicity correction across 29 comparisons.

### What this costs, and what survives

**What is lost.** The differentiating research question as registered. The pre-registration's section 1 claims two gaps: whether g has predictive value on business tabular data, and whether the classical baselines such comparisons rest on are tuned hard enough. The first is largely answered by Flórez-Ablan et al. The second is real and stands.

**What survives, because neither paper does it.** Imbalanced business tabular data at all. Average precision with an exact chance-level correction. Shuffled-label negative controls. Grid adequacy adjudicated against a shuffled null instead of argued from edge flags. A numerical conditioning floor bounding what any result in the study may claim. Per-record fitted classical surrogates run through the identical pipeline. Pre-registration, with its defects recorded as they were found.

**What is genuinely informative about the failure.** This pipeline independently re-derived a peer-reviewed result, with the correct mechanism, in four weeks, without knowing it existed. That is evidence the machinery is trustworthy, and it is worth more than the finding it reproduced. It is not, however, a contribution, and no part of this project may present it as one.

**The decision this forces.** *Taken on 25 September: the project turns toward the audit protocol. See section 14 for the reasoning and what the turn costs.* The choice was between the two readings below.

Either the project continues as a study and accepts that its central question is largely answered, or it turns toward the thing neither competing paper has: the audit protocol a quantum kernel comparison must pass, with churn and fraud as the worked example and the published literature as the demonstration of what the protocol catches. The second reading is what the list under "what survives" actually describes. It would also mean conceding that what has been built so far is one rigorous study rather than a benchmark: there is no public entry point, no results schema, no way to add a kernel without editing `FROZEN_SETTINGS`, and the churn licence forbids redistributing the data.

**Process change, effective immediately.** A literature check is the first task of any new research direction in this project, before a line of code, and its date and queries are recorded in the weekly record. Four weeks of work went past the point where one search would have changed the design.
