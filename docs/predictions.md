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

**Outcome.** Not yet run.

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

**Outcome.** Not yet run.

---

## Standing note on confounding

In the churn 250 table, fitted γ and qubit count are correlated, so P1 and P2 cannot both be cleanly attributed from that arm alone. Whichever survives out of sample, the write-up states that the two were confounded in the data that generated the hypotheses and says which arms broke the confound, rather than presenting the surviving variable as though it had been isolated.
