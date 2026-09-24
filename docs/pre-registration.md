# Pre-registration: quantum kernel methods on business tabular data, and the predictive value of the geometric difference

**Version 1.0. Registered 24 September 2026.**
Repository: `github.com/jnchowdary/qml-benchmark-lab`.
Code state this design rests on: commit `a8bafbb`. This document added at commit `61f7db9`.
The two differ because a document cannot contain its own commit hash; both are on `main` and public.
Author: Nagesh Chowdary, Diarka Quantum Ltd.

This document is registered **before any quantum kernel has been evaluated on real data**. Section 12 states exactly what was already observed at registration time, because a pre-registration that hides its starting point is worse than none.

---

## 1. Background and the gap

Huang et al. (2021, arXiv:2011.01938) proposed the geometric difference g(K_C‖K_Q) as a pre-training screen: computed from two Gram matrices alone, without training either model, it is claimed to bound when a quantum kernel could possibly outperform a classical one. g ≈ 1 is said to rule advantage out; g ≈ √n is said to leave it open.

The metric has been demonstrated mainly on constructed or biomedical data. Kakavand et al. (2026) benchmarked quantum kernels across nine UCI and OpenML datasets using kernel-target alignment rather than g, and found no significant advantage in 29 comparisons.

Two things are missing. First, whether g has predictive value on the tabular business data where classification is actually deployed — imbalanced, mixed-type, moderate-dimensional. Second, whether the classical baselines these comparisons rest on are tuned hard enough for a null result to mean anything.

This project addresses both. The classical side is already complete and is described in `docs/week-03-report.md`; its grids have been tested against a shuffled-label null and frozen. What remains, and what this document registers, is the quantum arm and the test of g.

---

## 2. Hypotheses

Three confirmatory tests. Everything else in the analysis is exploratory and is labelled as such wherever it appears.

**H1 — no quantum advantage in the primary cell.** For each dataset, the paired per-seed difference between the best quantum kernel and the best classical kernel, in the pre-specified primary cell, is zero. Two-sided. One test per dataset.

**H2 — the geometric difference carries no information.** Across all (dataset, mapping, qubit count, training size, quantum setting) units, g_λ(K_C‖K_Q) has no monotone relationship with the observed quantum-minus-classical difference. Two-sided, though the direction Huang et al. predict is positive.

**H3 — g has no negative predictive value.** Among units with g_λ below 2, the observed difference is not bounded nearer zero than among units above it. This is the operationally useful form of the claim: a practitioner wants to know whether a cheap screen can tell them not to bother.

H2 is the reason this project exists. H1 is the benchmark it is embedded in.

---

## 3. What is frozen

Every parameter below was set by a measurement recorded in `docs/week-03-report.md` and `docs/design-decisions.md`. None may change after registration except under section 11.

**Datasets.** Telco Customer Churn (Kaggle `blastchar/telco-customer-churn`, SHA-256 `88be4b93…`, 7,032 rows after cleaning, 30 features, 1,869 positives). Credit Card Fraud (Kaggle `mlg-ulb/creditcardfraud`, SHA-256 `76274b69…`, 284,807 rows, 29 features after dropping `Time`, 492 positives).

**Seeds.** 0 to 19. Fixed in `qbench.data.SEEDS`. Chosen from the measured paired variance: at 10 seeds churn's minimum detectable effect was 0.0324, larger than almost any effect this literature reports.

**Tracks.** Matched (class-balanced subsample, mapped to n_qubits dimensions, scaled to [0, π]) is the hypothesis-testing track and the only one on which g can be computed, since g needs both Gram matrices over the same points. Unconstrained (all features, up to 1,000 per class) is a reference ceiling, reported separately, never mixed into a paired test.

**Training sizes.** 50, 100 and 250 points per class, one output file each.

**Mappings.** PCA, Gaussian random projection, SelectKBest on mutual information (seeded).

**Qubit counts.** 4, 6, 8, 10, 12.

**Classical kernels and grids, frozen.** Linear; RBF with gamma 1e-3 to 1e2 in half-decades; polynomial with degree 2 to 5, scale-relative multiplier 0.1/1/3/10, coef0 in {0, 1}. C from 1e-4 to 1e4. These grids were tested for under-tuning by extending them in both directions and comparing against a shuffled-label null; the extension gained five to seven times more on random labels than on real ones, so they stand.

**Quantum kernels, frozen.** PennyLane embedding kernels: angle embedding and IQP embedding, each at 1 and 2 repetitions. Four structural settings, **all four run**, on `lightning.qubit`. No setting is screened out before the sweep; see section 5.

**Tuning.** Nested cross-validation: 20 outer seeds, 5-fold stratified inner CV on the outer-train portion only. `SVC(kernel="precomputed", class_weight="balanced")` for every kernel, classical and quantum alike, so folds, solver and selection rule are identical and only the Gram matrix differs. Selection is on inner-CV average precision. Grid points that fail to converge within 1,000,000 iterations are excluded, never scored.

**Primary cell.** The cell in which the classical baseline is strongest at 250 per class, determined from the already-observed week-3 data and named here so it cannot be chosen later: **churn = PCA at 12 qubits; fraud = SelectKBest at 8 qubits.** Choosing the classical baseline's strongest cell is the hardest test for a quantum advantage, and it is deliberate.

---

## 4. Endpoints and the decision rule

Two co-primary endpoints, both computed from the same stored per-test-point decision scores:

- **normAP** = (AP − chance) / (1 − chance), where chance is the exact expected average precision of a random ranking at that test-set size and positive count, computed by `qbench.metrics.chance_average_precision`. Not the base rate: a random ranker scores 0.5516 on 30 balanced test points and 0.5154 on 150.
- **ROC-AUC**, which has an exact null of 0.500 at any sample size.

**Decision rule: intersection-union. A hypothesis is rejected only if BOTH endpoints reject at alpha = 0.05, two-sided. No alpha correction is applied, because the type I error of "reject only if both reject" is at most that of either test alone.**

This was chosen by measurement, not preference. The two endpoints' paired differences correlate at a median of 0.818 to 0.947 across the matched arms (`results/analysis/endpoint_correlation.json`), so requiring both costs 4 to 8% on the minimum detectable effect, against 12% for splitting alpha across a union rule. On churn's unconstrained track the correlation is 0.429 and the union rule would be marginally cheaper; that arm carries no hypothesis and does not drive the rule.

**Test statistic.** Wilcoxon signed-rank on the 20 paired per-seed differences, two-sided. The paired t-test is reported alongside as a sensitivity check. Records are paired on the test-label fingerprint, which is asserted equal before any test is run; a mismatch aborts the analysis rather than being worked around.

---

## 5. Statistical power, declared in advance

Minimum detectable effect at 80% power under the intersection-union rule, from the measured median paired standard deviation in each arm:

| Arm | paired sd | MDE, single endpoint | MDE, intersection-union |
| --- | --- | --- | --- |
| churn matched, 50/class | 0.0604 | 0.0399 | **0.0427** |
| churn matched, 100/class | 0.0424 | 0.0280 | **0.0298** |
| churn matched, 250/class | 0.0241 | 0.0159 | **0.0171** |
| churn unconstrained | 0.0073 | 0.0048 | 0.0054 |
| fraud matched, 50/class | 0.0237 | 0.0157 | **0.0163** |
| fraud matched, 100/class | 0.0136 | 0.0090 | **0.0094** |
| fraud matched, 250/class | 0.0085 | 0.0056 | **0.0059** |
| fraud unconstrained | 0.0048 | 0.0032 | 0.0034 |

The primary cells sit at **0.0171 on churn and 0.0059 on fraud**. A null result at 250 per class therefore excludes a true advantage larger than those figures, and the paper will state it that way rather than as "no difference found".

**Declared underpowered in advance:** the 50-per-class arm on churn resolves only 0.0427 and would need 74 seeds to reach 0.020. It is run for the shape of the learning curve and is **not** used for hypothesis testing. Stating this now, rather than discovering it in the results, is the point of registering.

**Known limitation, stated and not corrected.** Seeds resample from one fixed dataset, so splits overlap and paired differences are not strictly independent. Expected shared test positives between two seeds: about 3 of 75 on churn (4%), about 11 of 75 on fraud (15%, because 250 positives per class are drawn from only 492 available). The tests are therefore mildly anti-conservative on fraud.

---

## 6. The geometric difference: how it is computed and tested

g is computed in its **regularised** form, `geometric_difference_regularised`, on normalised Gram matrices over the matched-track training set. λ is not chosen by hand: it is derived from the classical model actually being compared against, via `lambda_from_svm_C(C, n) = 1 / (2·C·n)`, using the C that inner-CV selected for that cell. A λ sweep is reported alongside every value, because g is sensitive to λ and an unregularised g exceeding its own √n ceiling means the classical kernel is under-regularised, not that the quantum kernel separates strongly.

**H2 test.** Spearman rank correlation between g_λ and the observed mean paired difference in normAP, across all 360 units (2 datasets × 3 mappings × 5 qubit counts × 3 training sizes × 4 quantum settings). Two-sided, alpha 0.05, single test. Reported within each dataset separately as a pre-declared secondary.

**H3 test.** Units split at g_λ = 2. Compare the distribution of |observed difference| above and below the split by Mann-Whitney U, two-sided, alpha 0.05. The threshold is fixed here and not tuned afterwards.

**Why g does not screen.** An earlier version of this design used g to reduce the quantum grid before the full sweep. That is circular: conditioning the experiment on g and then testing whether g predicts the outcome cannot answer the question. All four settings run. The cost is about 46 hours of compute against 34.

---

## 7. Controls

**Label-shuffled negative control.** The full quantum pipeline is run on permuted labels at the primary cell of each dataset, exactly as the classical pipeline already was. Expected ROC-AUC 0.500 and normAP 0. A consistent excess in both, beyond about two seed-level standard errors, halts the analysis until the cause is found. The classical control is already clean on all four files.

**Chance floor.** Every normAP is computed against the exact chance level, never the base rate. This is enforced in code and tested.

**Grid adequacy.** Any claim that a quantum feature-map grid is too narrow must be adjudicated by `scripts/check_grid_edges.py` against a shuffled-label null. **Hyperparameter edge flags alone will never be used to justify widening a grid**, because extending a grid raises the maximum inner-CV score even when no point is better — measured at five to seven times the real gain on the classical grids.

**Backend.** All quantum kernels run on `lightning.qubit`. A test asserts that `default.qubit` and `lightning.qubit` produce Gram matrices agreeing to 1e-8. Qiskit is used only as a single-setting cross-check and as the route to IBM hardware; framework wall-clock is never compared across frameworks.

**Cost metric.** Circuit evaluation counts, which are framework-independent, are the reported cost. Wall-clock is secondary and always labelled with its backend.

---

## 8. What counts as a result

**Advantage found.** Both endpoints reject in a primary cell, the difference favours the quantum kernel, and the shuffled control is clean. Reported with the effect size, its confidence interval, and the per-cell sweep as exploratory context.

**No advantage found.** Failure to reject, reported as an exclusion bound: "an advantage larger than 0.0171 normAP on churn and 0.0059 on fraud is excluded at 80% power", not as "no difference".

**g validated.** H2 rejected with a positive correlation, and H3 rejected in the direction that low g bounds the difference. This would make g a usable pre-training screen on business tabular data, which is the practically valuable outcome and the one this project was built to test.

**g not validated.** H2 not rejected. Given 360 units, this would be a meaningfully powered negative result about a metric the field currently takes on trust, and the paper leads with it.

All four outcomes are publishable and the paper is written the same way in each case.

---

## 9. Analysis plan and multiplicity

The confirmatory set is exactly three tests: H1 on churn, H1 on fraud, H2. H3 is confirmatory but subordinate to H2 and is reported only if H2 is rejected. No correction is applied across the two H1 tests, because they are separate questions about separate datasets, and this is stated in the paper.

Everything else — the 15-cell sweep per dataset, the qubit-count trend, the learning curve, the training-size comparison, per-mapping breakdowns — is **exploratory**. It is reported with Holm-corrected p-values within each family, labelled exploratory in every table caption, and no exploratory finding is described as evidence for or against H1 or H2.

**Search-size asymmetry, declared.** The classical side searches 396 grid points per cell (9 for linear, 99 for RBF, 288 for polynomial, counting the C grid); the quantum side searches 36 (four settings x nine C values). The classical search is therefore an order of magnitude wider, which given the measured relationship between grid size and inner-CV optimism favours the classical side on inner scores and not on the outer test estimate, which is what the tests use. The comparison is reported both as best-quantum-of-four against best-classical-of-three and per quantum setting against the best classical kernel, so a reader can see whether the headline depends on the quantum side getting to choose.

Selection of the best kernel within a cell, classical or quantum, is by inner-CV on the training folds only. The outer test set is touched once per (cell, seed, method), after selection. Inner-CV scores are never used to rank methods against each other, because inner-CV optimism rises with both grid size and small training sets: measured at +0.08 to +0.11 PR-AUC at 70 training points on churn.

---

## 10. Reproducibility

Python 3.13, `requirements.txt` pinned exactly (qiskit 2.4.2, qiskit-machine-learning 0.9.1, pennylane 0.45.1, pennylane-lightning 0.45.0, numpy 2.4.4, scipy 1.17.1, scikit-learn 1.8.0). `requirements.lock.txt` carries the full resolved set. CI runs the suite on every push; 189 tests at registration, `qbench` coverage 96%.

Every result record stores its git commit, the C grid, the seed, the per-test-point decision scores, the test labels and an order-sensitive label fingerprint. Raw data is never committed; `data/README.md` carries provenance, checksums and licences. The churn licence forbids redistribution.

---

## 11. Deviations

Any departure from this document will be recorded in `docs/deviations.md` with its date, its reason, and whether it was made before or after the affected results were seen, and will be reported in the paper. A deviation made after seeing results is not forbidden but is declared as such and the affected analysis is labelled exploratory.

---

## 12. What was already observed at registration

Stated in full, because it determines how much this registration is worth.

**Complete and analysed:** the entire classical arm. Both datasets, both tracks, three training sizes, 20 seeds, 15 cells per matched file, 900 records per file. Classical grids tested for under-tuning and frozen. The label-shuffled classical control, clean on all four files. The compute benchmark on the target machine. The power analysis that set the seed count. The endpoint-correlation analysis that set the decision rule.

**Known from that work, and used to fix this design:** the minimum detectable effect in every arm; that churn's best classical cell is PCA at 12 qubits and fraud's is SelectKBest at 8; that linear beats nonlinear only where the mapping already aligns the data; that fraud is saturated at every training size; that inner-CV optimism rises steeply as training sets shrink; and that a wider hyperparameter search gains more on shuffled labels than on real ones.

**Never run, on either dataset, in any form:** any quantum kernel on real data. No Gram matrix from `angle` or `iqp` has been computed on churn or fraud. No value of g(K_C‖K_Q) has been computed on real data. The quantum modules have been exercised only on synthetic data in tests and on random arrays in the compute benchmark.

So H1, H2 and H3 are untouched by anything observed so far. The design around them is not blind, and is not claimed to be.

---

## 13. Timeline

Week 4: build the quantum kernel path and run the four settings across the matched track, about 46 hours of compute. Week 5: compute g across all units. Week 6: primary tests. Weeks 7 to 8: IBM hardware runs on the primary cells. Week 9: statistics and the exploratory sweep. Weeks 10 to 12: writing.

---

*Registered at OSF. Any version of this document other than the registered one is a draft.*
