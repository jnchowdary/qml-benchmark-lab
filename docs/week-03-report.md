# QML Benchmark Lab: Week 3 Record

Written 23 September 2026. Covers work done 22 to 23 September 2026.
Results produced at commit `2cf7ec7` on `main`. 175 tests passing, `qbench` coverage 96%, `tuning.py` 100%.
The chance-AP correction in section 7 landed after those runs and is analysis-only: no experiment was re-run for it.

---

## 1. What week 3 was for, and what it turned into

Week 3's job was the classical baselines: tune every classical kernel properly, on two tracks, across enough seeds to support a paired comparison in week 9. That work finished on 22 September and met its acceptance criteria.

Then a question was asked that the plan never asks: what has been missed that becomes impossible to fix later? Six gaps came out of one pass. Four were closed, and closing them changed the experimental design more than the original week-3 work did. This record covers both halves, because the second half is the part that matters.

The uncomfortable summary is that the first half of the week produced a pipeline which passed every test it had been given and could not have supported the paper it exists to produce. It stored no per-test-point predictions, so no paired significance test was possible without re-running everything. Nobody had asked what effect size ten seeds can resolve. There was no negative control. The compute budget came from a Linux container rather than the machine that runs the experiments.

---

## 2. The design as it now stands

| | Before 22 September | After 23 September |
| --- | --- | --- |
| Seeds | 10 | 20 (0..9 preserved as a prefix) |
| Qubit counts | 2, 3, 4, 6, 8 | 4, 6, 8, 10, 12 |
| Training sizes (matched) | 250 per class | 50, 100, 250 per class |
| Mappings | PCA, random projection, SelectKBest | unchanged |
| Kernels | linear, RBF, polynomial | unchanged |
| Per-test-point predictions | not stored | stored, with an order-sensitive fingerprint |
| Negative control | none | label-shuffled run at 250 per class |
| Simulator for week 4 | undecided | `lightning.qubit`, benchmarked |

Every change was decided from a measurement taken this week, not from preference. The justifications are in sections 4 to 6.

Records per file: 900 for each matched track file (20 seeds x 3 mappings x 5 qubit counts x 3 kernels), 60 for each unconstrained file. Six matched files, two unconstrained, four negative-control files.

---

## 3. Why the gaps existed

Recorded because the cause is structural and will recur otherwise.

The plan was written by the same party that then executed it and checked the results against the plan's own acceptance criteria. A gap the plan did not name was a gap nothing in the process would surface. Week 3's criteria said "tuned classical baselines, ten seeds, edge flags clean"; those were met, and nothing asked whether the output would still be usable in week 9.

The second cause is that every error caught in three weeks was caught by a measurement that returned a wrong number: the geometric difference reading 72.1 against a ceiling of 3.46, the non-deterministic mapping scoring 0.5199 then 0.5664 on identical input, the ten-minute polynomial hang, the plateau misread as a slope, the fraud base rate printing 0.330. That method works, and it only finds faults in things that produce numbers. A missing pre-registration produces no number. Neither does an un-run power calculation or an un-run negative control. Four of the six gaps were invisible to the only detector in operation.

The remedy adopted, cheap enough to actually happen: at the start of each week, write into that week's report what this week produces that week 9 will need in a form not currently stored, and what becomes unrecoverable if deferred. Anything answering "unrecoverable" jumps the queue regardless of the plan's calendar. At weeks 6 and 9, a second pass asks what a hostile referee would demand.

---

## 4. Statistical power: the measurement that changed the design

`scripts/power_analysis.py` takes the paired per-seed differences between classical kernels within a cell, which have the same structure the week-9 quantum-versus-classical comparison will have, and solves the minimum detectable effect exactly from the non-central t distribution.

On the ten-seed data, churn's median paired standard deviation was 0.0325 PR-AUC, giving a minimum detectable effect of 0.0324 with 80% power at alpha 0.05. That is larger than almost any effect this literature reports. A null churn result from that design would have been a statement about sample size, not about quantum kernels.

Minimum detectable effect on the twenty-seed data, from the median paired standard deviation in each file:

| File | median paired sd | MDE at 20 seeds | worst cell | seeds for 0.020 |
| --- | --- | --- | --- | --- |
| churn matched, 50/class | 0.0604 | 0.0399 | 0.0846 | 74 |
| churn matched, 100/class | 0.0424 | 0.0280 | 0.0565 | 38 |
| churn matched, 250/class | 0.0241 | 0.0159 | 0.0368 | 14 |
| churn unconstrained | 0.0073 | 0.0048 | 0.0050 | 4 |
| fraud matched, 50/class | 0.0237 | 0.0157 | 0.0470 | 14 |
| fraud matched, 100/class | 0.0136 | 0.0090 | 0.0313 | 6 |
| fraud matched, 250/class | 0.0085 | 0.0056 | 0.0225 | 4 |
| fraud unconstrained | 0.0048 | 0.0032 | 0.0037 | 3 |

The primary arm, matched at 250 per class, now resolves 0.0159 on churn and 0.0056 on fraud. Both are below the 0.020 target. The 50-per-class arm resolves 0.0399 on churn and would need 74 seeds to reach 0.020; it is underpowered by design and is present for the shape of the learning curve, not for hypothesis testing. That is declared in advance rather than discovered afterwards.

Two hard limits no effect size can move. At 20 paired seeds a two-sided sign test needs 15 of 20 wins to reach p = 0.05, and the Wilcoxon signed-rank floor is well below 0.05, so the rank tests are usable at this seed count. At the 10 seeds originally planned, the sign test needed 9 of 10.

Seeds were chosen over a larger subsample because the two are not equally priced. Doubling seeds costs twice the quantum compute and takes churn's MDE from 0.0324 to 0.0215 on the old cell set; doubling the subsample costs four times the compute, because kernel cost is quadratic in sample size, and reaches only 0.0229. Widening the test fraction would have been cheaper still and was rejected: it would have changed the split and broken comparability with everything already measured.

A caveat for the pre-registration. Seeds resample from one fixed dataset, so the splits overlap and the paired differences are not strictly independent. For churn, the expected shared test positives between two seeds is about 3 of 75, or 4%. For fraud, where 250 positives per class are drawn from only 492 available, it is about 11 of 75, or 15%. The t-test is therefore mildly anti-conservative on fraud. Stated, not corrected.

---

## 5. The compute model, measured on the machine that will run week 4

The figures the schedule had been built on (9.0 ms per kernel entry for Qiskit, 2.2 ms for PennyLane) came from a Linux container. `lightning.qubit` had never been benchmarked at all. Measured on the MacBook Air, macOS 26.2, arm64:

| Qubits | lightning.qubit | default.qubit | Qiskit statevector |
| --- | --- | --- | --- |
| 4 | 0.401 ms | 0.550 ms | 2.847 ms |
| 6 | 0.440 ms | 0.670 ms | 3.964 ms |
| 8 | 0.477 ms | 0.754 ms | 5.089 ms |
| 10 | 0.550 ms | 1.032 ms | - |
| 12 | 0.650 ms | 1.598 ms | - |
| 14 | 0.985 ms | - | - |
| 16 | 2.249 ms | - | - |

The container figures were pessimistic by three to four times. Qiskit's statevector path is 7.1 to 10.7 times slower than lightning, and the gap widens with qubit count, which settles the framework question: everything in week 4 runs on PennyLane with `lightning.qubit`, and Qiskit remains as a single-setting cross-check and as the route to IBM hardware. `build_pennylane_kernel` now takes a `device` argument and records it, and a test asserts that the backends produce identical Gram matrices, because a faster backend that quietly changes the numbers is worse than a slow one.

The shape of the curve mattered more than its level. Cost rises 1.10, 1.08, 1.15 and 1.18 times per step from 4 to 12 qubits, then 1.52 to 14 and 2.28 to 16. Below 12 qubits the cost is Python dispatch, not linear algebra. Qubit count in the 4-to-12 range is therefore nearly free, which makes the sweep a scientific choice rather than a budget one. The plan's `{4, 6, 8}` clustered three measurements inside the flat region; `{4, 6, 8, 10, 12}` spans a real lever arm and reaches the regime where fidelity kernels are known to concentrate toward the identity, which matters because concentration pushes the geometric difference toward its ceiling and reads as "advantage not ruled out" when it is a pathology.

Week 4 at these rates, with the structural grid pre-screened from twelve settings to three by the geometric difference, is about 34 hours: four to five overnight runs.

---

## 6. Per-test-point predictions

`tune_and_evaluate` now stores `test_decision_scores`, `test_labels` and `test_label_fingerprint` on every record. An average precision of 0.8192 cannot be turned back into a paired test; the 150 numbers behind it can. McNemar, DeLong and a paired bootstrap all need the individual predictions, and without them week 9 would have meant re-running every experiment to obtain a p-value.

The fingerprint is a hash of the test labels in order. Two records may only be paired if they were scored on the same points in the same order, and week 9 will assert that rather than trusting that identical seeds produced identical splits. All eight result files report 900 of 900 or 60 of 60 records carrying scores, and 20 of 20 seeds sharing one fingerprint across their cells.

The cause of this gap is worth recording: `tune_and_evaluate` returned a summary record because a summary was what week 3's table needed. Designing the output format around its immediate consumer is how a project ends up re-running everything to get a statistic.

---

## 7. The negative control, and the error in reading it

Labels are permuted within the subsample before the split, preserving class counts exactly, with a seed offset so the permutation is reproducible and independent of the split it is paired with. The entire pipeline then runs on labels that carry no signal: mapping, angle scaling, nested cross-validation, tuning, final fit, scoring.

The first reading of the output appeared to show a leak. PR-AUC came in 0.0192 above the base rate on churn and 0.0223 above on fraud, at roughly 2.2 and 2.5 seed-level standard errors, and the verdict block printed at the time asserted that the expectation was the base rate.

**That assertion is false.** A random ranking's average precision is upward-biased at finite sample size, because average precision averages precision taken at the rank of each positive and the first positive lands near the top more often than the mean suggests. The bias shrinks as the number of positives grows:

| test points | positives | base rate | chance AP |
| --- | --- | --- | --- |
| 30 | 15 | 0.5000 | 0.5516 |
| 60 | 30 | 0.5000 | 0.5312 |
| 150 | 75 | 0.5000 | 0.5154 |
| 448 | 148 | 0.3304 | 0.3389 |
| 600 | 300 | 0.5000 | 0.5050 |

Read against the correct null, the control is clean:

| File | ROC-AUC | sigma from 0.500 | AP minus chance | sigma from 0 |
| --- | --- | --- | --- | --- |
| churn matched 250 | 0.5078 | +0.76 | +0.0038 | +0.43 |
| churn unconstrained | 0.4901 | -1.79 | -0.0062 | -1.29 |
| fraud matched 250 | 0.5058 | +0.58 | +0.0069 | +0.76 |
| fraud unconstrained | 0.5031 | +0.47 | +0.0046 | +0.97 |

Mixed signs, all within two sigma, and the worst single cell (ROC-AUC 0.6549) is the maximum of 900 correlated draws where chance alone predicts about 0.648. The pipeline does not leak.

`src/qbench/metrics.py` now computes the chance level exactly, from the order-statistic distribution of the positives' ranks, evaluated in log space. It is verified against the analytic single-positive case, where expected AP is the nth harmonic number divided by n, and against sklearn's own scorer under simulation. Both checks are independent of the derivation, which is the point: this was the third time in this project that an expected value was asserted from intuition and turned out to be wrong, after the plateau misreading and the fraud base rate. It nearly happened a fourth time the same day, when 0.9386 was written into a power test from memory and the solver returned 0.9960; the simulation sided with the solver.

---

## 8. What the chance-AP correction invalidated

Paired comparisons are unaffected. Within a cell every method sees the same test set, so the chance level is a shared constant that cancels exactly in the difference. Every figure in section 4 and every planned week-9 paired test is safe.

Comparisons across test-set sizes are affected, and the training-size sweep is exactly such a comparison. The earlier `normAP` helper divided by one minus the base rate and was optimistic, most so for the smallest test sets. Corrected, churn's PCA at 12 qubits with a linear kernel reads:

| Training size | raw AP | chance AP | corrected normAP |
| --- | --- | --- | --- |
| 50 per class | 0.7527 | 0.5516 | 0.4484 |
| 100 per class | 0.8079 | 0.5312 | 0.5902 |
| 250 per class | 0.8192 | 0.5154 | 0.6269 |

The raw climb of 0.0665 is really 0.1785. The learning curve is nearly three times steeper than raw average precision shows.

---

## 9. The learning curve

Best cell per training size, corrected normAP:

| | 50/class | 100/class | 250/class | unconstrained |
| --- | --- | --- | --- | --- |
| Churn | 0.4948 (pca/4, linear) | 0.6021 (pca/10, rbf) | 0.6268 (pca/12, linear) | 0.6427 |
| Fraud | 0.9607 (selectk/10, linear) | 0.9606 (selectk/12, poly) | 0.9684 (selectk/8, linear) | 0.9608 |

Churn climbs and then flattens: most of the gain is between 50 and 100 points per class, and the step from 250 per class to the full 1,000-per-class unconstrained track is only 0.0159.

Fraud is flat. It reaches 0.9607 on 70 training points and 0.9684 on 350, and the unconstrained track with 1,044 training points and all 29 features scores 0.9608, which is below the matched track's best. The training-size sweep was recommended partly as a fix for fraud's ceiling effect; **it is not one.** Fraud's strongest cells are saturated at every training size. The sweep does work for PCA and random projection, where there is room to climb, and it is a legitimate learning-curve measurement of the small-data regime the quantum-kernel literature makes its claims about, but it did not open headroom where fraud is strongest. That recommendation was oversold when it was made and is corrected here.

The fraud result is interesting in its own right: eight mutual-information-selected features on 350 points beat all 29 features on 1,044 points. The signal is concentrated and the extra features are noise.

---

## 10. Qubit count

Corrected normAP at 250 per class, from 4 to 12 qubits:

| Mapping | Churn | Fraud |
| --- | --- | --- |
| PCA | 0.6170 to 0.6268 (+0.0098) | 0.9285 to 0.9548 (+0.0263) |
| Random projection | 0.3678 to 0.5481 (+0.1803) | 0.7930 to 0.9289 (+0.1359) |
| SelectKBest | 0.5216 to 0.5881 (+0.0665) | 0.9524 to 0.9677 (+0.0153) |

PCA is essentially flat: four principal components already carry what churn has to give, which is consistent with week 2's finding that signal saturates early. Random projection gains the most, which is what a signal-agnostic projection should do as dimensions are added. The `{4, 6, 8}` sweep in the plan would have captured under half of the random-projection climb and shown nothing at all for PCA. The wider sweep has already earned its cost.

---

## 11. Linear against nonlinear, and what week 3 got wrong earlier

Week 3's first pass concluded that the linear kernel reaches the ceiling and the classical side is not under-tuned. With five qubit counts and twenty seeds that conclusion needs qualifying: it depends on the mapping.

At 250 per class, corrected normAP, linear minus the better nonlinear kernel. On churn PCA the linear kernel wins at every qubit count, by 0.0077 to 0.0201. On churn random projection the RBF kernel wins at 4 to 8 qubits, by 0.0295 to 0.0461, and the gap closes by 12 qubits. On churn SelectKBest the three kernels are within 0.011 of each other. On fraud the RBF kernel wins on PCA by 0.0022 to 0.0099 and on random projection by 0.0198 to 0.0543, and SelectKBest is a three-way tie within 0.002.

So "linear is enough" holds where the mapping already aligns the data (PCA on churn, SelectKBest anywhere) and fails where it does not (random projection everywhere, PCA on fraud). For week 6 this means the quantum kernels must be compared against the best classical kernel **per cell**, not against a single globally chosen reference.

---

## 12. Inner-CV optimism scales with training size, not just grid size

Week 3's first pass found that inner-CV optimism rises with grid size. With three training sizes, the larger effect is visible: optimism is driven by how little data the inner folds have.

Inner score minus outer test score, churn, by kernel:

| Training size | linear (grid 9) | RBF (grid 99) | poly (grid 288) |
| --- | --- | --- | --- |
| 50 per class (70 train) | +0.0762 | +0.1084 | +0.1063 |
| 100 per class (140 train) | +0.0423 | +0.0561 | +0.0546 |
| 250 per class (350 train) | +0.0068 | +0.0177 | +0.0199 |
| unconstrained (1,400 train) | -0.0002 | +0.0027 | +0.0022 |

At 56 effective training points per inner fold, cross-validation overstates performance by 8 to 11 points of PR-AUC. On fraud the same pattern appears but compressed by the ceiling: +0.0073 to +0.0174 at 50 per class, +0.0001 to +0.0023 at 250.

This is directly relevant to the literature being positioned against. A small-data quantum machine learning result reported from cross-validation scores rather than a held-out test set is inflated by roughly this much, and the inflation is larger for the method that searched more settings.

Model selection itself is close to random in the small-data regime. The inner-CV winner is also the test winner in 34% of churn cells at 50 per class, 37% at 100 and 30% at 250, against a 33% chance rate. Fraud reaches 48% at 250 per class. Always choosing the linear kernel beats trusting the inner-CV winner by 0.0026 on churn at 250 per class, and loses to it by 0.0062 on fraud.

---

## 13. The squeeze cost, corrected

Churn: the matched track's best cell reaches corrected normAP 0.6268 against the unconstrained track's 0.6427. Twelve dimensions and 350 training points cost 0.0159 against thirty features and 1,400 points. On raw average precision the same comparison reads 0.0039, because the matched track's smaller test set sits on a higher chance floor; the corrected figure is four times larger and is the honest one.

Fraud: the matched track's best cell **exceeds** the unconstrained track, 0.9684 against 0.9608. The squeeze costs nothing and mutual-information selection helps.

Good for fairness, bad for the optimistic quantum case: if a few dimensions and a few hundred points lose almost nothing classically, there is little room for a quantum kernel to recover.

---

## 14. The one thing not yet clean: grid edges

Between 265 and 350 of the 900 tuned models in each matched file chose a hyperparameter at the edge of its searched range, and the plateau-aware rule removed none of them. The concentration is specific. On churn at 250 per class, 94 of 300 RBF models chose the smallest gamma in the grid and 133 of 300 polynomial models did the same; the C grid is barely touched, with 1 to 27 flags.

Under-tuning the classical baseline is the most common way this literature manufactures an apparent quantum advantage, so a third of models sitting at a grid boundary cannot be called tuned. The likely reading is that both kernels want gamma small enough to behave almost linearly, which would make this a plateau the current tolerance is too strict to detect, but that is a hypothesis and it has not been measured.

This must be settled before the quantum runs, because the classical reference has to be credible. The test is cheap: extend the RBF gamma grid below 1e-3 and the polynomial multiplier below 0.1, re-run churn at 250 per class only, and check whether the flags move to the new edge and whether any test score changes materially. Half an hour of machine time. It is the first item of week 4.

---

## 15. Tests, coverage and housekeeping

175 tests passing, up from 137. `qbench` coverage 96%. `tuning.py` at 100%. Two new test files: `test_audit_fixes.py` (23 tests, one per closed gap plus the design decisions) and `test_metrics.py` (14 tests on the chance-AP calculation).

Tests worth naming, because each encodes a failure rather than a feature. The stored decision scores must reproduce the reported metric exactly, or week 9's p-value would describe a different model from week 3's table with nothing to announce it. The label fingerprint must be order-sensitive, because a hash that ignored order would license an invalid pairing. The training-size sweep must write separate files, because a size silently mixed into a within-cell pairing would be invisible. A shuffled run must never overwrite a real one. The power solver must deliver the power it claims, verified by simulating the test it describes. And the backends must agree to 1e-8, because a fast backend computing something else is not a speedup.

Environment: `pip install -r requirements.txt` downgraded numpy from 2.5.3 to the pinned 2.4.4 and scipy from 1.18.1 to 1.17.1. The pre-22-September results were therefore produced on different numerics from the ones now pinned. Everything in this record was produced after the downgrade. `pennylane-lightning==0.45.0` is now pinned explicitly; it was already installed as a PennyLane dependency and already the backend `lightning.qubit` resolved to, but an unpinned transitive dependency is not a record of which simulator set the compute budget.

The ten-seed results are archived at `results/runs/classical/archive-week3-10seeds/` rather than deleted, so the 20-seed files do not silently replace them. That directory is gitignored along with the rest of `results/runs/`, so it is local only and is regenerable from the archived commit.

---

## 16. Decisions taken this week

Twenty seeds, justified by the measured paired variance in section 4, with 0 to 9 preserved as a prefix so every earlier run stays a subset of every later one. Qubit counts 4, 6, 8, 10, 12, justified by the flat cost curve in section 5. Training sizes 50, 100 and 250 per class, with the 50 arm declared underpowered in advance. `lightning.qubit` as the sole simulator for week 4, with Qiskit as a cross-check and the hardware route. Average precision normalised against the exact chance level, never the base rate, for any comparison across sizes, tracks or datasets. ROC-AUC reported alongside, as the one measure with an exact null at any sample size.

SMOTE stays out of the main pipeline. Both tracks use class-balanced subsampling, which makes resampling redundant, and adding it would introduce a synthetic-data confound into the one comparison the project exists to make.

---

## 17. Still open

The pre-registration is written next, and it now has real numbers to carry: the seed count and its justification, the minimum detectable effect per arm, the declared-underpowered arm, the frozen quantum feature-map grids, the metric definitions, and the analysis plan. It is the one remaining item whose value decays with every day it is delayed.

The quantum structural grids are still not frozen, while the classical ones are. That asymmetry is exactly the freedom a referee would attack, and it closes with the pre-registration.

The grid-edge question in section 14. The IBM Quantum Open Plan allocation is still unconfirmed. The pre-registration mechanism, OSF or a published hash, is still unchosen. And the Kaggle credential file remains somewhere on the machine that neither of us has located.

---

## 18. Week 4

In order: settle the grid edges; write and timestamp the pre-registration with the numbers from this record; freeze the quantum feature-map grids inside it; then build the quantum kernels and pre-screen the structural grid with the geometric difference on one seed before committing 34 hours of compute to a full sweep.

---

## 19. Corrections (23 September 2026)

Four, all mine, all recorded because the pattern matters more than the individual errors.

**The negative-control expectation.** The verdict block asserted that a random ranker's average precision equals the test base rate. It does not, at finite sample size. Read against the base rate, a clean pipeline appeared to leak at 2.2 and 2.5 sigma. Fixed in `qbench/metrics.py` with an exact calculation, validated two independent ways. Section 7.

**normAP normalised against the base rate.** Same root cause. The helper was optimistic, most so for the smallest test sets, which is precisely where the learning curve needed it to be right. Corrected; it understated the churn learning curve's slope by a factor of nearly three and the squeeze cost by a factor of four. Sections 8, 9 and 13.

**The training-size sweep sold as a fix for fraud's ceiling.** It is a learning-curve measurement, not a power fix. It raises resolution slightly on fraud's weaker cells and lowers it on churn, and fraud's strongest cells are saturated at every training size. Section 9.

**A remembered constant in a power test.** 0.9386 was written in as the required effect size for a paired t-test at n = 10; the correct value is 0.9960, and 0.9386 delivers 75% power rather than 80%. Caught only because a solver had been written to disagree. The test now carries the simulation that settled it.

The common thread with the plateau misreading in week 3's first pass and the fraud base-rate error: a number held with confidence, written into code as an assertion, never checked against anything independent. Every expectation introduced from here on gets an independent check in the same commit, or it does not go in.
