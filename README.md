# QML Benchmark Lab

Two things live here.

**An audit protocol** for quantum-classical kernel comparisons: a set of checks that tell you whether a comparison was set up so its answer could mean anything. It audits method, not results, and it runs against any pipeline that can emit a documented record format. See [`docs/audit-protocol.md`](docs/audit-protocol.md).

**The study it came out of**, written as a pre-registration but never externally registered (see D11): quantum kernel SVMs against tuned classical kernel SVMs on imbalanced business tabular data (customer churn, credit-card fraud), with the geometric difference g(K_C‖K_Q) of Huang et al. as a pre-training screen. See [`docs/pre-registration.md`](docs/pre-registration.md).

The protocol is the part worth reusing. It exists because every check in it was written after a specific reading went wrong here, usually one that had already passed review.

## Status

Week 12 of 12; the paper is assembled at [`docs/paper.md`](docs/paper.md), generated from its sections by `scripts/assemble_paper.py`. The classical and quantum arms are complete: **15,120 result records** — 7,440 classical, 7,520 quantum, 160 negative-control — across two datasets, three training sizes, 15 configurations and 20 seeds. **All three registered confirmatory hypotheses have been tested.** H1 rejects on churn in the classical kernel's favour and does not reject on fraud. **H2 and H3 return no verdict**: no lambda column is free of ceiling breaches, so D5's decision rule does not resolve. That is the rule declining to speak and not a finding of no relationship — at the largest lambda the null is rejected in the predicted direction, accounts for 2.9% of rank variance, and reverses sign across the sweep. **Three lambda rules have now been evaluated**, including the one Huang's own source prints, which selects no lambda at all on 76.5% of the units; see D16. 19 test files, and `scripts/geometric_tests.py` now carries 30 of its own plus a mutation harness that checks they are not vacuous.

The audit now reaches the kernels. Three of the four checks it had declared unrunnable were not: `tuning symmetry` needed nothing and is Tier 1, `kernel conditioning` and `classical surrogate equivalence` needed only an interface and run against any pipeline supplying `--hook`. Those are the checks that would have caught this project's two largest defects, and both were invisible from records alone.

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
    --compare CLASSICAL.jsonl \
    --hook scripts/audit_hook_qbench.py
```

`--hook` is optional and points at a three-function adapter for your own pipeline; without it the checks that need kernels say so and name what they needed.

The record format is eight fields, none of them quantum-specific. Full specification in [`docs/audit-protocol.md`](docs/audit-protocol.md).

## What the study found

Reported as results, not as advantage claims.

**One of eight arms produced a difference its own comparison could resolve.** Every other observed value here is smaller than that arm's minimum detectable effect, which is neither evidence of equivalence nor a measurement of a small effect. Power figures are regenerated from the records by `scripts/audit_sweep.py` rather than transcribed, and each is labelled with the comparison it describes: an exclusion bound on a primary test quotes the variance of the pair that test forms, not a median over every method pair in the cell.

**H1, churn primary cell (PCA at 12 qubits, 250 per class): rejected, favouring the classical kernel.** normAP −0.0798 (95% CI −0.1229 to −0.0367, Wilcoxon p = 8.2e−05), ROC-AUC −0.0292 (p = 3.4e−04), both endpoints, intersection-union rule.

**H1, fraud primary cell (SelectKBest at 8 qubits): not rejected.** An advantage larger than 0.0063 in normAP is excluded at 80% power, on a problem where both arms sit at 0.966 and only 0.034 of headroom exists.

**The registered grid gave the classical arm eleven bandwidths and the quantum arm none.** Correcting that collapses the churn rejection to −0.0101 (p = 0.076), which is below the corrected arm's own resolution of 0.0233 — the rejection collapses, and what replaces it is not a measured near-zero. But 19 of 20 seeds then choose a bandwidth below 1.0, where an angle fidelity kernel is provably a Gaussian kernel with γ = (reps·b)²/4 — confirmed on real data to within 2%, with Spearman 0.999999 against the predicted RBF. The gap closes exactly as the kernel becomes classical.

**A classical surrogate fitted to each quantum kernel, no labels, same pipeline, scores what the quantum kernel scores** at every tuned bandwidth. At the registered bandwidth `iqp-r1` beats its nearest RBF by +0.0852 while losing to the best classical kernel by −0.1011: genuinely non-classical and genuinely worse. All 160 fitted γ values fall inside the classical RBF grid searched since week 2.

**On fraud at tuned bandwidths the quantum kernels are Gaussian kernels the classical baseline had already searched.** All four settings, twenty seeds each: every interval spans zero, both families fall below the precision floor (angle +0.0002, IQP −0.0008), and 80 of 80 fitted γ values sit inside the 1e−3 to 1e2 grid `run_classical_baselines.py` searched in week 2 — before the quantum arm existed.

**Churn's tuned arm is a weaker result and is reported as one.** Angle −0.0033 [−0.0076, +0.0010], IQP +0.0045 [−0.0036, +0.0126]: no detected effect, but both point estimates are three to four times the precision floor and what fails is the interval excluding zero, not the magnitude. That is an underpowered null, not the sub-floor identity fraud shows, and it needs more seeds rather than more analysis.

**`angle-r2` collapses on every SelectKBest cell**, mean −0.1934, replicated at all five qubit counts. The most reproducible effect in the study, and it is quantum structure costing rather than earning.

## How the work is disciplined

| document | what it holds |
| --- | --- |
| [`docs/pre-registration.md`](docs/pre-registration.md) | v1.0, frozen. Hypotheses, design, declared power, decision rule. Never edited; errors in it are corrected by deviation records. |
| [`docs/deviations.md`](docs/deviations.md) | Eighteen records. Each states its date, its reason, and whether it was made before or after the affected results were seen. D3, D6 and D11 record defects in the pre-registration itself; D10 is marked POST-HOC in its own heading and records three wrong explanations before the one that held. |
| [`docs/predictions.md`](docs/predictions.md) | Exploratory claims written down with falsification conditions **before** the run that tests them. Outcomes are appended, never edited, including a withdrawn bound. |
| `docs/week-0N-report.md` | Weekly records, weeks 1 to 9. Week 4 logs eleven errors and names the pattern behind three of them. |
| `docs/week-10-12-report.md` | The closing record for the registered writing phase, weeks 10 to 12, kept as one record because the phase was one. |

Weeks 4 to 9, the weeks 10 to 12 record and `deviations.docx` are generated from their records by `scripts/report_to_docx.js`. **Weeks 1 to 3 were transcribed into Word by hand**, before that generator existed, and are not regenerated; `scripts/check_docx_fresh.py` reports them as provenance-unrecorded rather than assuming they match. That checker exists because the generator alone did not prevent drift: on 15 October 2026 `deviations.docx` was found sixteen days behind a record that had since doubled in length.

## Use of AI assistance

This project was built with substantial assistance from Claude (Anthropic), working through Claude Code, from 17 September 2026. The division of labour was:

**Assisted.** Implementation of the pipeline, the analysis scripts and the audit protocol; drafting of the pre-registration, the deviation records, the prediction log and the weekly reports; and the identification of several defects in the work, including the bandwidth asymmetry in the registered grid, the classical limit of the tuned kernels, and the power-analysis error recorded in D6.

**Not assisted.** The research question, the experimental design, every decision recorded in `docs/deviations.md`, the execution of every experiment, and the judgement of what the results mean. All runs were executed by the author on the author's hardware. No result in this repository was produced by a model.

**How the assistance was checked, which is the part worth reading.** The assistant's errors are logged rather than summarised: eleven are numbered in section 10 of `docs/week-04-report.md`, each with the specific measurement that caught it, and further ones are recorded in D6 and in `tests/test_audit.py`, where several failures are preserved as test cases carrying the numbers that exposed them. Three were caught only by reading output rather than by any test. Two were found inside the audit protocol itself, by the audit protocol, including one instance of the same unit-of-analysis error that the tool warns its users about.

That log is the evidence for this declaration. A claim that AI output was verified is worth little; a list of what verification caught, with the arithmetic, is worth more.

**How this is recorded in the history, and why it changes partway through.** The assistance is
declared here, in prose, and not as `Co-Authored-By` trailers on individual commits. Commits
made before 25 September 2026 originally carried such trailers; they were removed by a history
rewrite on that date, which changed every commit hash in the project. Commits between 26 and 29
September carry them again, because they were reinstated by default without the change being
noticed. From 29 September the convention is prose only. The inconsistent stretch is left in
place rather than rewritten, because rewriting history is what broke this project's
pre-registration hashes in the first place; the third amendment to D11 in
[`docs/deviations.md`](docs/deviations.md) records the whole sequence.

**For citation or submission**, the paragraph below is the form intended for a methods or declarations section. Confirm the exact model identifier at submission time rather than copying it from here.

> Portions of this work were produced with assistance from Claude (Anthropic), used for software implementation, analysis tooling and documentation drafting between September 2026 and the date of submission. The research question, experimental design, execution of all experiments and interpretation of all results are the author's. Assistant-generated code and analysis were reviewed by the author, and errors identified during that review are enumerated in the project's public record at `docs/week-04-report.md` and `docs/deviations.md`, including two defects found within the project's own audit tooling. No experimental result was generated by a model.

## Reproducing

Raw data is never committed. `data/README.md` carries provenance and checksums; the churn licence forbids redistribution, so you need your own Kaggle credentials. Python 3.13, `requirements.txt` pinned exactly, `requirements.lock.txt` for the full resolved set. Every record stores its git commit, the C grid, the seed, the per-test-point decision scores, the test labels, and an order-sensitive label fingerprint.

Quantum kernels are computed from statevectors rather than pairwise circuits — identical to 1e−15, about 100x faster, and recorded as deviation D1. **Reported cost stays the pairwise circuit count**, n(n−1)/2, with the simulator shortcut counted separately, so no claim here rests on something a quantum computer cannot do. That count is not QPU time: hardware runs each pairwise circuit once per shot, and deviation **D18** records that D1, D12, the week 8 record, this file and §3.7 of the paper, plus three source files, called the count a hardware-equivalent cost until 25 October 2026.

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

Maintainer: Nagesh Kumar Jonnalagadda, Diarka Quantum Ltd. Licence: see `LICENSE`.
