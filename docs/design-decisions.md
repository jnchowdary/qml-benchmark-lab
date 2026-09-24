# QML Benchmark Lab — frozen design decisions

Last updated 24 September 2026. Full detail in `docs/week-03-report.md` in the repo, commit `132a6ea`.

## The experiment as it now stands

Twenty seeds (`qbench.data.SEEDS = range(20)`, with 0..9 kept as a prefix so earlier runs stay a subset). Qubit counts 4, 6, 8, 10, 12. Matched-track training sizes 50, 100 and 250 per class, one output file each. Three mappings (PCA, Gaussian random projection, SelectKBest on mutual information) and three classical kernels (linear, RBF, polynomial). Datasets: Telco churn and ULB credit-card fraud.

Each of these came from a measurement taken in week 3, not from preference:

- **20 seeds** because the measured median paired sd gave a minimum detectable effect of 0.0324 PR-AUC on churn at 10 seeds, larger than almost anything this literature reports. At 20 seeds the primary arm (250 per class) resolves 0.0159 on churn and 0.0056 on fraud.
- **Qubits to 12** because `lightning.qubit` costs only 1.6x more at 12 qubits than at 4 on the target machine; the knee is at 12, then 1.52x to 14 and 2.28x to 16.
- **Training-size sweep** as a learning-curve measurement of the small-data regime. The 50-per-class arm is declared underpowered in advance (MDE 0.0399 on churn, would need 74 seeds for 0.020).
- **`lightning.qubit` as the sole simulator** for week 4. Qiskit statevector is 7 to 11x slower and stays as a one-setting cross-check plus the IBM hardware route.
- **Classical hyperparameter grids frozen as they are** — RBF gamma 1e-3 to 1e2, polynomial degree 2 to 5 with multipliers 0.1 to 10 — because extending them was measured against a shuffled-label null and found to buy noise (see below).

## Metric rules

Average precision is normalised against the **exact chance level**, never the base rate. A random ranker's AP exceeds the base rate at finite sample size: 0.5516 at 30 balanced test points, 0.5154 at 150, 0.5050 at 600. `qbench.metrics.chance_average_precision` computes it exactly. Paired within-cell comparisons are unaffected (the floor cancels); any comparison across training sizes, tracks or datasets must use normAP against chance, or ROC-AUC, which has an exact null of 0.5 at any sample size.

## Established findings

**A wider hyperparameter search helps more when there is no signal.** Extending the classical grids in both directions (degrees to 9, multipliers 0.003 to 100, RBF gamma 1e-5 to 1e4) gained +0.0016 mean on real churn labels against +0.0080 on shuffled ones, and +0.0008 against +0.0055 on fraud. Degree-up winners are commoner under the null (10 of 15 against 5 on churn). The winning degree scatters across the whole range on real data, which is a flat noisy surface rather than an optimum outside the grid. Read alongside the inner-CV optimism result below, this is one finding: in the small-data regime, searching harder produces a better cross-validation number and a worse-behaved selection. That is a statement about the field's methodology and belongs in the paper.

Consequence for the pipeline: edge flags are **descriptive, not diagnostic**. They report a value on a boundary; `scripts/check_grid_edges.py` against a shuffled null adjudicates whether that matters. The plateau tolerance detects exact ties only, because selection noise (~0.008) exceeds the smallest detectable effect (0.0056) and no tolerance can absorb one without hiding the other.

Inner-CV optimism is driven by training-set size more than grid size: on churn it is +0.08 to +0.11 PR-AUC at 70 training points and +0.007 to +0.020 at 350. Inner-CV model selection is near chance in the small-data regime (30 to 37% correct against 33% chance).

"Linear is enough" depends on the mapping: linear wins on churn PCA, RBF wins on random projection and on fraud PCA, SelectKBest is a tie. Week 6 must compare quantum kernels against the best classical kernel **per cell**.

Fraud is saturated at every training size in its strongest cells (normAP 0.96 to 0.97 throughout), and eight selected features on 350 points beat all 29 features on 1,044. Churn's squeeze cost (12 dimensions, 350 points versus 30 features, 1,400 points) is 0.0159 in corrected normAP.

The label-shuffled negative control is clean on all four files once read against the correct null.

## Open, in priority order

1. Pre-registration, with the numbers above in it. The one item whose value decays daily. It must declare one analysis decision that came out of the grid work: quantum feature-map grids get compared against a shuffled-label null before any grid is called too narrow, and edge flags alone never justify widening one.
2. Quantum feature-map grids still unfrozen while the classical ones are frozen.
3. IBM Quantum Open Plan allocation unconfirmed; pre-registration mechanism (OSF or published hash) unchosen.
4. Kaggle credential file still unlocated on the machine.

## Process note

Seven interpretation errors so far, all from one cause: a number or rule held with confidence, written into code as an assertion, never checked against anything independent (the C-plateau misread as a slope, the fraud unconstrained base rate, the chance-AP floor, a remembered power constant, a one-sided grid diagnostic, a verdict rule that measured the winner's curse, a plateau tolerance chosen to look reasonable). The last three were caught by controls built for the purpose rather than by an output looking wrong — the first time that has happened in this project. Rule: every expectation introduced gets an independent check in the same commit.
