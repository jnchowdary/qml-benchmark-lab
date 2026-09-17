# QML Benchmark Lab

**Does the geometric difference g(K_C‖K_Q) predict, before you train anything, whether a quantum kernel SVM can beat a tuned classical one on real business tabular data?**

That is the question. This is not a "can quantum beat classical" bake-off — that has been run, most recently by [Kakavand, Strohmeyer & Schlotter (2026)](https://arxiv.org/abs/2604.18837), who found no significant advantage in 29 comparisons across 9 UCI/OpenML datasets. What they did not do is use Huang et al.'s geometric difference as a *pre-screen*, and they did not use business data (fraud/churn). Those two gaps are this project.

A null result is a valid outcome here and is the expected one.

## Status

Week 1 of 12. Environment verified, kernels implemented and property-tested, pipeline runs end to end. No experimental results yet.

## Quick start

```bash
python -m pip install -r requirements.txt
make test     # 75 tests, ~10s
make quick    # end-to-end demo, ~3 min
```

`make quick` needs no Kaggle credentials — it runs on a synthetic dataset. Its output is **a demo, not evidence**: 2 seeds, fixed hyperparameters, 100 rows.

## Methods

| Family | Method | Implementation | Measured cost (4 qubits) |
| --- | --- | --- | --- |
| Classical | Linear SVM | scikit-learn | negligible |
| Classical | RBF SVM | scikit-learn | negligible |
| Classical | Polynomial SVM | scikit-learn | negligible |
| Quantum | ZZ feature map, reps=1,2,3 | Qiskit `FidelityQuantumKernel` | ~9.0 ms/entry |
| Quantum | Angle embedding | PennyLane `default.qubit` | ~2.2 ms/entry |
| Quantum | IQP embedding | PennyLane `default.qubit` | ~2.2 ms/entry |
| Quantum | Trainable kernel (QKT) | Qiskit — *week 8* | not yet measured |

**Framework overhead is a confound.** Qiskit and PennyLane differ by ~4x on identical work. Runtime comparisons across frameworks measure the framework, not the kernel. Report circuit-evaluation counts as the primary cost metric.

## Cost model

Quantum kernels cost n²/2 circuit evaluations. From measured rates:

| n | entries | Qiskit build time |
| --- | --- | --- |
| 100 | 4,950 | ~45 s |
| 250 | 31,125 | ~4.7 min |
| 500 | 124,750 | ~19 min |

The full 284,807-row credit-card fraud set would be ~10¹⁰ circuit evaluations. Class-balanced subsampling to n≤500 for the quantum track is a hard constraint, not a preference.

## Reading a g value

`g ≈ 1` means the classical kernel reproduces the quantum one and advantage is **ruled out**. `g ≈ √n` means advantage is **not ruled out** — which is not evidence of one.

**g is unstable if you compute it carelessly.** Measured on random 12×12 kernel pairs, g at λ=1e-8 ranged from 9.1 to 72.1 against a ceiling of √12=3.46, tracking cond(K_C) almost exactly. Computed without regularisation, g measures how ill-conditioned your classical kernel is. The protocol:

1. Always use `geometric_difference_regularised` with an explicit λ.
2. Set λ from the classical SVM's own C via `lambda_from_svm_C`.
3. Report `g_lambda_sweep`, not a single number.
4. Hold λ fixed across every cell in a reported figure — g moves >5x across the plausible λ range, which swamps any real between-cell difference.
5. g > √n means under-regularised, not "large separation". The code warns.

## Significance testing

Paired tests across ≥10 seeds on bit-identical folds (Shapiro-Wilk → Wilcoxon signed-rank or paired t), Holm-Bonferroni across all pairwise comparisons, effect sizes reported alongside every p-value. Results state plainly which comparisons survived correction, including when none do.

## Honest takeaways

Nothing to report yet — week 1. This section will state where classical won, in the first paragraph, not in a caveats appendix.

## Citations

- Havlíček et al. (2019), *Supervised learning with quantum-enhanced feature spaces*, Nature 567.
- Huang et al. (2021), *Power of data in quantum machine learning*, Nat. Commun. 12:2631. [arXiv:2011.01938](https://arxiv.org/abs/2011.01938)
- Kübler et al. (2021), *Numerical evidence against advantage with quantum fidelity kernels on classical data*. [arXiv:2211.16551](https://arxiv.org/abs/2211.16551)
- Kakavand, Strohmeyer & Schlotter (2026), *Benchmarking Quantum Kernel SVMs Against Classical Baselines on Tabular Data*. [arXiv:2604.18837](https://arxiv.org/abs/2604.18837)

## Contact

Maintainer: Nagesh — Diarka Quantum Ltd. Licence: see `LICENSE` (decision pending).
