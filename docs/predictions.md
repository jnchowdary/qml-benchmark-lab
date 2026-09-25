# Exploratory predictions, registered before the run that tests them

## Why this file exists

`docs/deviations.md` disciplines the registered design. Nothing disciplines the exploratory claims, and week 4 showed what that costs.

On 25 September an exploratory prediction was made about the RBF-surrogate gap, tested on churn at 250 per class, and failed. A replacement explanation was then found **by inspecting the same table that killed the first one**, and reported with p = 2.2e−05. That p-value does not account for the search that produced it: fifteen cells, and at least three candidate explanatory variables (fitted γ, qubit count, mapping) visible at once. It is the same structure as extending a hyperparameter grid until the score improves, which week 3 measured and rejected on the classical side.

An explanation fitted to the data that refuted its predecessor is a hypothesis, not a finding. This file exists so that such hypotheses are written down, dated, and given a falsification condition **before** the run that could confirm them, and so that a reader can see which exploratory claims were predictions and which were descriptions.

Rules: an entry is added before the run that tests it, never after. Entries are never edited once a result exists; outcomes are appended. A failed prediction stays in the file.

---

## P1. The IQP surrogate gap grows with qubit count

**Registered 25 September 2026, before any surrogate run on fraud or on churn at 100 and 50 per class.**

**Where it came from, stated plainly.** Post-hoc, from the churn 250-per-class registered arm, after a different prediction (that the gap would track fitted γ) failed on that same table. It is not a registered hypothesis, carries no confirmatory weight, and is reported as exploratory wherever it appears.

**The claim.** For `iqp-r1`, the gap between the quantum kernel and its own best-fit RBF, measured out of sample in normAP, increases with the number of qubits.

**The evidence it was built on, which cannot also test it.** Churn, 250 per class, registered arm, 15 cells: Spearman(n_qubits, gap) = +0.873, p = 2.2e−05. Means by qubit count +0.0404, +0.0142, −0.0118, −0.0150, −0.0261 at 12, 10, 8, 6, 4.

**What is predicted, on data that contributed nothing to it.**

* **P1a, fraud registered arm, 250 per class, 15 cells, `iqp-r1`.** Spearman(n_qubits, gap) is positive with p < 0.05.
* **P1b, churn registered arm at 100 and 50 per class, `iqp-r1`.** Spearman(n_qubits, gap) is positive in both, with the point estimate at 250 (+0.873) falling inside a reasonable range of the others rather than being an outlier.
* **P1c, directional detail.** The mean gap is negative at 4 and 6 qubits and positive at 12, in each arm where P1a or P1b holds.

**What falsifies it.** A non-positive Spearman in fraud's registered arm, or in either churn training size. A positive correlation in only one of the three. A sign pattern that does not reproduce P1c.

**Known weakness of this test, stated in advance so a null is not over-read.** Fraud is saturated: both arms sit at normAP 0.966 with roughly 0.034 of headroom, and every surrogate gap in its primary cell falls within ±0.01. A ceiling can suppress a real trend, so a null on P1a is weaker evidence against the claim than a positive result would be for it. P1b is the stronger of the two: same dataset but different subsamples and different training sizes, so partially independent rather than fully.

**What each outcome licenses.**

* All three hold: the trend is a property of the IQP kernel rather than of one arm, and it may be described as such in the paper, still labelled exploratory and still carrying the note that it was found post-hoc.
* P1b holds and P1a does not: report as a churn-specific trend with the fraud ceiling given as the reason the cross-dataset test is uninformative, not as a partial confirmation.
* P1b fails: the trend was an artefact of one arm. It is reported as a failed prediction in this file and removed from the week-4 record's section 8, which currently states it as the reading of that table.

**What it does not claim, in any outcome.** Nothing here is an advantage. At its strongest cell the `iqp-r1` kernel beats its own nearest RBF by +0.0852 and loses to the best classical kernel by −0.1011. A kernel that is not an RBF is not thereby a good kernel.

**Outcome, 25 September 2026. HELD, in all three arms, including the independent dataset.**

| arm | Spearman(qubits, gap) | p | mean gap at 12 / 6 / 4 qubits |
| --- | --- | --- | --- |
| fraud 250 (independent dataset) | **+0.961** | 1.2e−08 | +0.0121 / −0.0020 / −0.0074 |
| churn 100 | +0.698 | 3.8e−03 | +0.0669 / −0.0240 / −0.0353 |
| churn 50 | +0.720 | 2.5e−03 | +0.0924 / −0.0072 / −0.0550 |
| churn 250 (generated the hypothesis, not a test) | +0.873 | 2.2e−05 | +0.0404 / −0.0150 / −0.0261 |

P1a holds. P1b holds in both arms, and the churn 250 estimate falls between the others rather than being an outlier. P1c holds everywhere: positive at 12 qubits, negative at 6 and 4, in every arm.

Note on the arm I called weaker in advance: fraud gave the cleanest ordering of the four while compressing magnitudes to roughly a tenth of churn's. That is what a ceiling does — it shrinks effects without disturbing rank — and it means the saturation caveat registered above was right about magnitude and wrong about power.

**Confound identified after the result, and NOT yet ruled out.** The gap is quantum minus surrogate. At higher qubit counts the quantum kernel concentrates, so its best-fit RBF has larger γ and is a more localised, worse classifier. A gap growing with qubit count is therefore also consistent with the *comparator degrading* while the quantum kernel stays flat, which would remove the quantum content from P1 entirely. Distinguishing the two needs the absolute normAP of both arms by qubit count. The script records this per row, but the first three runs all wrote to one filename and overwrote each other, so only the logs survived and the logs do not carry absolute levels. `trend_stats` now prints both columns and the runs must be repeated before P1 is described as a property of the quantum kernel anywhere.

**Confound TESTED and rejected, 25 September 2026, on the re-run with absolute levels preserved.** For `iqp-r1` the quantum arm's own normAP rises with qubit count in every arm, and faster than its surrogate:

| arm | quantum, 4 → 12 qubits | surrogate, 4 → 12 qubits |
| --- | --- | --- |
| fraud 250 | 0.8850 → 0.9392 (+0.054) | 0.8923 → 0.9271 (+0.035) |
| churn 100 | 0.3944 → 0.4887 (+0.094) | 0.4297 → 0.4218 (−0.008) |
| churn 50 | 0.2807 → 0.3822 (+0.102) | 0.3357 → 0.2898 (−0.046) |

On fraud the comparator improves as well, so none of the gap is comparator decay. On churn 50 roughly a third of the gap growth is surrogate decay and two thirds is quantum gain. The alternative explanation is real but secondary and does not carry the result.

**Correction to the statistics reported above, 25 September 2026.** The first version of `trend_stats` correlated over all 300 records rather than the 15 cells, treating twenty seeds of one configuration as twenty independent observations of a trend. It reported fraud `angle-r2` at rho −0.149 with p 0.0099 on a column where every gap sat at or below D2's 1e−3 precision floor. The Spearman values in the table above are the cell-level ones, n = 15, and those are the ones this project reports. The row-level figures printed in the first re-run are void.

**Status: held as stated, confound rejected, mechanism now the leading explanation but still exploratory and still not an advantage.** The `iqp-r1` kernel improving faster than its nearest RBF as qubits rise says it is not a classical kernel in disguise. It says nothing about whether it beats the best classical kernel, which it does not.

---

## P2. The `angle-r2` collapse is a SelectKBest phenomenon mediated by fitted γ

**Registered 25 September 2026, before any surrogate run on fraud or on churn at 100 and 50 per class.**

**Where it came from.** Same table, same caveat as P1: descriptive, not predictive, in its origin.

**The claim.** `angle-r2`'s large negative surrogate gap appears where the fitted γ is small (broad RBF), which on churn means the SelectKBest mapping, and not where γ is near 1.

**The evidence it was built on.** Churn 250, registered arm: Spearman(γ, gap) = +0.802, p = 3.3e−04; Spearman(n_qubits, gap) = +0.316, p = 0.25. Means by mapping: SelectKBest −0.1934, PCA −0.0070, random projection −0.0046. All five SelectKBest cells clear the three conditions after Holm.

**What is predicted, out of sample.**

* **P2a.** In fraud's registered arm and in churn at 100 and 50, the correlation between fitted γ and `angle-r2`'s gap is positive and stronger than its correlation with qubit count.
* **P2b.** Where a mapping fits γ below roughly 0.2, `angle-r2`'s mean gap is more negative than −0.05; where it fits γ near or above 1, the gap is within ±0.03.

**What falsifies it.** γ correlating no better than qubit count, or large negative gaps appearing at γ near 1, or the mapping split not tracking γ.

**Why this one is more likely to hold than P1.** It has a mechanism that does not depend on the dataset: a doubled-angle kernel compared against a broad RBF is a comparison between a sharply varying kernel and a nearly flat one, and the mismatch should grow as the best-fit RBF flattens. P1 has a plausible mechanism too, but a weaker one, and P1's variable is confounded with γ in the data that produced it.

**Outcome, 25 September 2026. PARTIALLY HELD. The strong half holds; the weak half fails; one arm cannot test it at all.**

* **P2a holds on both churn arms.** Spearman(γ, gap) +0.836 (p 1.0e−04) at 100 per class and +0.823 (p 1.7e−04) at 50, against qubit-count correlations of −0.060 (p 0.83) and +0.109 (p 0.70). γ is the correlate and qubit count is not, as predicted.
* **P2a fails on fraud, but degenerately.** γ there is −0.119 (p 0.67) and qubits −0.235 (p 0.40), neither significant. Every fraud cell fits γ between 1.00 and 1.12, so there is almost no variation in γ to correlate against. Recorded as uninformative rather than as a failure of the claim.
* **P2b, first half: holds.** Every cell fitting γ below 0.2 is a SelectKBest cell with a gap beyond −0.13. Mean −0.2132 at 100 per class (n=5) and −0.2341 at 50 (n=5), against −0.0191 and −0.0365 for everything else.
* **P2b, second half: FAILS.** The prediction was that cells with γ at or above 0.2 stay within ±0.03. They do not: `pca/6` reaches −0.0455 at 100 per class and −0.0705 at 50, and `pca/4` −0.0600 at 50. The threshold was stated too tightly and the failure is recorded rather than the threshold moved.
* **On fraud, no mapping fits γ below 1.0 at all**, so P2b's antecedent never fires there. That is untestable, not passed, and the script now says so in those words rather than printing a vacuous pass.

**Status: the γ-mediated SelectKBest collapse is confirmed out of sample on churn and untested elsewhere; the quantitative bound in P2b is withdrawn.**

---

## Standing note on confounding

In the churn 250 table, fitted γ and qubit count are correlated, so P1 and P2 cannot both be cleanly attributed from that arm alone. Whichever survives out of sample, the write-up states that the two were confounded in the data that generated the hypotheses and says which arms broke the confound, rather than presenting the surviving variable as though it had been isolated.
