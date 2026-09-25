# The audit protocol

A quantum-classical kernel comparison can be run carefully and still mean nothing, because the ways it fails are not visible in its results. This document specifies a set of checks that are, and a record format that makes them runnable against any pipeline.

It audits **method, not results**. It never reports which model won. A failure means a conclusion drawn from a file is not supported *by* that file; it does not mean the conclusion is wrong.

Implementation: `scripts/audit.py`. Tests: `tests/test_audit.py`.

---

## 1. Why these checks and not others

Each one exists because a specific reading went wrong in this project, usually after passing review. They are not a general statistics checklist. The date and the damage are given for each in section 4.

Two published benchmarks in this area — [Flórez-Ablan, Roth & Schnabel (2025)](https://doi.org/10.1088/2058-9565/ade7ad) and [Kakavand, Strohmeyer & Schlotter (2026)](https://arxiv.org/abs/2604.18837) — between them perform none of: chance-corrected average precision, shuffled-label negative controls, grid adequacy adjudicated against a shuffled null, a numerical conditioning floor, or classical surrogate equivalence. The second, at 970 experiments across nine datasets with hardware validation, also appears to omit bandwidth tuning entirely and multiplicity correction across its 29 comparisons. The gap this protocol addresses is not another comparison.

---

## 2. The record format

One JSON object per line. Nothing is specific to quantum kernels: a record is **one model, scored once, on one train/test split**.

### Required

| field | type | meaning |
| --- | --- | --- |
| `method` | str | what was fitted, e.g. `rbf` or `quantum-iqp-r1` |
| `seed` | int | identifies the split; records sharing a seed share a train/test partition |
| `n_train`, `n_test` | int | split sizes |
| `test_base_rate` | float | positive fraction in the test set |
| `test_average_precision` | float | raw AP, uncorrected |
| `test_roc_auc` | float | |

### Strongly recommended

Checks degrade to SKIP without these, and say which question each missing field makes unanswerable.

| field | type | what it enables |
| --- | --- | --- |
| `test_label_fingerprint` | str | hash of the test labels **in order**. Without it no paired test can be verified, only assumed. |
| `shuffled` | bool | marks a permuted-label control record |
| `final_converged` | bool | false if the solver hit its iteration cap |
| `inner_score` | float | the selection score, so it can be shown selection used training folds |

### Configuration

A *configuration* (or cell) is a setting the comparison is repeated across: a feature mapping, a qubit count, a training size. Records sharing a configuration and a seed are one split scored by different methods, which is what makes them pairable.

Supply it either as a nested `cell` dict, or as top-level fields and let the audit infer them. **The inference rule:** a configuration field varies across records but not across the methods being compared, so every one of its values is scored by the same set of methods. That distinguishes `mapping` and `n_qubits` (configurations) from `embedding` and `reps` (arms of the comparison, since each of their values is scored by only some methods).

The inferred grouping is always printed. Override with `--cell-fields`.

### Two arms

The comparison usually spans two files: quantum results and classical results. Pass the second with `--compare`. Without it, every power and multiplicity figure describes comparisons *within* one arm, which is generally not the comparison being tested. See D6.

---

## 3. The checks

### Tier 1 — runnable from records alone

| check | what it asserts | fails when |
| --- | --- | --- |
| schema | required fields present | any required field missing from any record |
| chance correction | AP is comparable across the file | test sets of differing shapes, so raw AP spans two null levels |
| negative control | a permuted-label run sits at its null | deviation exceeds both 2 sigma **and** the reproducibility floor |
| pairing integrity | records paired together were scored on the same points | fingerprints differ within a (seed, configuration) group |
| solver health | no scored model hit its iteration cap | any `final_converged` false |
| unit of analysis | the reader knows which n a p-value rests on | always warns when configurations exist; the number is the point |
| statistical power | the minimum detectable effect is stated | warns when coarse relative to reported effects |
| precision floor | no difference below the pipeline's reproducibility limit is treated as a measurement | any method pair differs by less than `--floor` |
| multiplicity | the number of available comparisons is declared | more than one comparison without a stated correction |
| cross-arm comparison | the two arms pair on verified identical test points, and the power reported is the power of the comparison being made | groups do not pair, or pair on different test points |
| selection | selection used an inner score, not the reported test score | inner scores absent, so it cannot be shown |

### Tier 2 — not runnable from records alone

Reported as NOT RUN with the reason. Claiming a check happened when it could not is the failure this tool exists to catch, so it is honest about itself first.

| check | why it needs more than records |
| --- | --- |
| kernel conditioning | needs the Gram matrices. An ill-conditioned kernel makes the SVM dual underdetermined, so decision scores move at machine precision and any threshold-based test is invalid. |
| classical surrogate equivalence | needs kernels and training data. A quantum kernel that scores what its fitted nearest classical kernel scores **is** that kernel, whatever its Spearman distance. |
| grid adequacy against a shuffled null | needs a re-run on permuted labels with a widened grid. Widening raises the best inner score even when nothing is better, so hyperparameter edge flags never justify it. |
| bandwidth tuning | needs the embedding. A fidelity kernel at a fixed data scale is not a tuned model, and the classical arm almost always gets a bandwidth grid while the quantum arm almost never does. |

---

## 4. What each check is for, with the failure that motivated it

**Chance correction.** A random ranker's average precision exceeds the base rate at finite n: 0.5154 on 150 balanced points, 0.5516 on 30. Comparing raw AP across test-set sizes compares two different nulls. In week 3 this made a clean pipeline read as a 2.2-sigma leak, and normalising against the base rate instead of exact chance understated a learning curve threefold.

**Negative control.** The only evidence a pipeline does not leak. It must clear **both** a sigma bar and the reproducibility floor: the first version of this check divided by a standard error of 1e-22 on near-identical records and reported 3.5e16 sigma on a mean deviation of 0.000014.

**Pairing integrity.** Two kernels scored on different test points cannot be paired, and a silent mismatch is invisible in the summary metrics.

**Unit of analysis.** Twenty seeds inside one configuration are one configuration observed twenty times. Correlating across 300 records rather than 15 configurations turned a column of sub-floor noise into p = 0.0099. This project made that error four times, the last inside the check written to explain it.

**Statistical power and cross-arm.** A null result excludes effects *larger* than the minimum detectable effect and says nothing smaller. Worse, power measured within one arm is not the power of a two-arm comparison: this project's registered figure of 0.0171 came from classical-versus-classical variance and the true cross-arm figure is 0.0608, off 3.6x. See D6.

**Precision floor.** Kernels at condition number 1e16 to 1e19 give a reproducibility floor near 1e-3 in average precision. Below it a difference is not a small effect, it is below the arithmetic resolution of the pipeline. Set it with `--floor` for your own pipeline; the default is this project's measured value.

**Multiplicity.** Fifteen configurations times six method pairs is ninety comparisons and a 0.99 chance of at least one spurious rejection uncorrected. Declare which are confirmatory in advance, or correct.

**Selection.** Choosing the arm by its test score turns a held-out estimate into a maximum over candidates, biased upward.

---

## 5. Usage

```bash
# one arm
PYTHONPATH=src python scripts/audit.py RESULTS.jsonl

# the whole comparison
PYTHONPATH=src python scripts/audit.py RESULTS.jsonl \
    --control RESULTS_shuffled.jsonl \
    --compare CLASSICAL.jsonl \
    --floor 1e-3 \
    --json report.json
```

`--cell-fields a b` overrides the inferred configuration grouping. Exit code is 0 when everything passed or skipped, 1 on any warning, 2 on any failure.

---

## 6. What this protocol does not do

It does not tell you whether a quantum kernel is better. It does not detect a wrong implementation of a kernel, a mis-specified feature map, or a dataset that leaks its labels through preprocessing. It cannot see any analysis you performed outside the file it is given. A clean report means the file supports the kind of claim you are making, not that the claim is true.

It was also wrong on the first real file it saw: it required a nested `cell` field that this project's own pipeline never emitted, collapsed fifteen configurations into one, and silently changed three answers. That is the argument for running it against real data rather than fixtures, and for printing the inferred grouping where a reader can check it.
