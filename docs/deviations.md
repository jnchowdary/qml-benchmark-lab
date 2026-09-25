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
