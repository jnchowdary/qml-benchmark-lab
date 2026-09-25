# QML Benchmark Lab

Two things live here.

**An audit protocol** for quantum-classical kernel comparisons: a set of checks that tell you whether a comparison was set up so its answer could mean anything. It audits method, not results, and it runs against any pipeline that can emit a documented record format. See [`docs/audit-protocol.md`](docs/audit-protocol.md).

**The pre-registered study it came out of**: quantum kernel SVMs against tuned classical kernel SVMs on imbalanced business tabular data (customer churn, credit-card fraud), with the geometric difference g(K_C‖K_Q) of Huang et al. as a pre-training screen. See [`docs/pre-registration.md`](docs/pre-registration.md).

The protocol is the part worth reusing. It exists because every check in it was written after a specific reading went wrong here, usually one that had already passed review.

## Status

Week 5 of 12. The classical and quantum arms are complete: 5,400 classical and 7,200 quantum records, two datasets, three training sizes, 15 configurations, 20 seeds. H1 has been tested under the registered rule. 341 tests.

**The study's central question was largely answered elsewhere before we asked it.** [Flórez-Ablan, Roth & Schnabel (2025)](https://doi.org/10.1088/2058-9565/ade7ad) showed that bandwidth tuning cures the concentration that makes fidelity kernels fail, but only by turning them into classical kernels. We derived the same result independently and with the right mechanism, fourteen months later, because nobody ran a literature search until week 4. That is recorded in section 15 of [`docs/week-04-report.md`](docs/week-04-report.md) and it is why the project turned toward the protocol.

## Quick start

```bash
python -m pip install -r requirements.txt
make test
```

Audit a results file:

```bash
PYTHONPATH=src python scripts/audit.py RESULTS.jsonl \
    --control RESULTS_shuffled.jsonl \
    --compare CLASSICAL.jsonl
```

The record format is eight fields, none of them quantum-specific. Full specification in [`docs/audit-protocol.md`](docs/audit-protocol.md).

## What the study found

Reported as results, not as advantage claims.

**H1, churn primary cell (PCA at 12 qubits, 250 per class): rejected, favouring the classical kernel.** normAP −0.0798 (95% CI −0.1229 to −0.0367, Wilcoxon p = 8.2e−05), ROC-AUC −0.0292 (p = 3.4e−04), both endpoints, intersection-union rule.

**H1, fraud primary cell (SelectKBest at 8 qubits): not rejected.** An advantage larger than 0.0063 in normAP is excluded at 80% power, on a problem where both arms sit at 0.966 and only 0.034 of headroom exists.

**The registered grid gave the classical arm eleven bandwidths and the quantum arm none.** Correcting that collapses the churn rejection to −0.0101 (p = 0.076). But 19 of 20 seeds then choose a bandwidth below 1.0, where an angle fidelity kernel is provably a Gaussian kernel with γ = (reps·b)²/4 — confirmed on real data to within 2%, with Spearman 0.999999 against the predicted RBF. The gap closes exactly as the kernel becomes classical.

**A classical surrogate fitted to each quantum kernel, no labels, same pipeline, scores what the quantum kernel scores** at every tuned bandwidth. At the registered bandwidth `iqp-r1` beats its nearest RBF by +0.0852 while losing to the best classical kernel by −0.1011: genuinely non-classical and genuinely worse. All 160 fitted γ values fall inside the classical RBF grid searched since week 2.

**`angle-r2` collapses on every SelectKBest cell**, mean −0.1934, replicated at all five qubit counts. The most reproducible effect in the study, and it is quantum structure costing rather than earning.

## How the work is disciplined

| document | what it holds |
| --- | --- |
| [`docs/pre-registration.md`](docs/pre-registration.md) | v1.0, frozen. Hypotheses, design, declared power, decision rule. Never edited; errors in it are corrected by deviation records. |
| [`docs/deviations.md`](docs/deviations.md) | Six records. Each states its date, its reason, and whether it was made before or after the affected results were seen. D3 and D6 record defects in the registered document itself. |
| [`docs/predictions.md`](docs/predictions.md) | Exploratory claims written down with falsification conditions **before** the run that tests them. Outcomes are appended, never edited, including a withdrawn bound. |
| `docs/week-0N-report.md` | Weekly records. Week 4 logs twelve errors and names the pattern behind four of them. |

Weekly documents are generated from their records by `scripts/report_to_docx.js`, not transcribed.

## Reproducing

Raw data is never committed. `data/README.md` carries provenance and checksums; the churn licence forbids redistribution, so you need your own Kaggle credentials. Python 3.13, `requirements.txt` pinned exactly, `requirements.lock.txt` for the full resolved set. Every record stores its git commit, the C grid, the seed, the per-test-point decision scores, the test labels, and an order-sensitive label fingerprint.

Quantum kernels are computed from statevectors rather than pairwise circuits — identical to 1e−15, about 100x faster, and recorded as deviation D1. **Reported cost stays hardware-equivalent** at n(n−1)/2 circuit evaluations; the simulator shortcut is counted separately, so no claim here rests on something a quantum computer cannot do.

## Reading a g value

`g ≈ 1` means the classical kernel reproduces the quantum one and advantage is ruled out. `g ≈ √n` means advantage is not ruled out, which is not evidence of one.

g is unstable if computed carelessly. Deviation D5 records why: λ set from the classical model's own C reaches 1.4e−06 here, at which g returns **57.3 for a kernel provably equal to an RBF**, against a √n ceiling of 18.71. Always use `geometric_difference_regularised` with an explicit λ, report the full sweep rather than a single value, exclude units breaching their ceiling and report the count, and require any conclusion to hold across every λ in the sweep.

## Citations

- Havlíček et al. (2019), *Supervised learning with quantum-enhanced feature spaces*, Nature 567.
- Huang et al. (2021), *Power of data in quantum machine learning*, Nat. Commun. 12:2631. [arXiv:2011.01938](https://arxiv.org/abs/2011.01938)
- Kübler et al. (2021), *Numerical evidence against advantage with quantum fidelity kernels on classical data*. [arXiv:2211.16551](https://arxiv.org/abs/2211.16551)
- Shaydulin & Wild (2022), *Importance of kernel bandwidth in quantum machine learning*. [arXiv:2111.05451](https://arxiv.org/abs/2111.05451)
- Flórez-Ablan, Roth & Schnabel (2025), *On the similarity of bandwidth-tuned quantum kernels and classical kernels*, Quantum Sci. Technol. [doi:10.1088/2058-9565/ade7ad](https://doi.org/10.1088/2058-9565/ade7ad)
- Kakavand, Strohmeyer & Schlotter (2026), *Benchmarking Quantum Kernel SVMs Against Classical Baselines on Tabular Data*. [arXiv:2604.18837](https://arxiv.org/abs/2604.18837)

## Contact

Maintainer: Nagesh Chowdary, Diarka Quantum Ltd. Licence: see `LICENSE`.
