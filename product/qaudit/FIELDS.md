# The record format, field by field, and what goes dark without each

One JSON object per line. A record is **one model, scored once, on one
train/test split**. Nothing in the format is specific to quantum kernels.

`template.jsonl` holds three records in the shape below: one hardware quantum
arm, its classical comparator on the same split, and the same quantum setting
on a simulator. Copy it and replace the values.

## Required

Without any one of these, `schema` returns FAIL and the checks that name it
return SKIP. The rest still answer, which is the point of listing them
separately.

| field | type | meaning |
| --- | --- | --- |
| `method` | str | what was fitted, e.g. `rbf` or `quantum-iqp-r1` |
| `seed` | int | identifies the split; records sharing a seed share a partition |
| `n_train` | int | training points |
| `n_test` | int | test points |
| `test_base_rate` | float | positive fraction in the test set |
| `test_average_precision` | float | raw AP, uncorrected |
| `test_roc_auc` | float | |

What each absence costs:

* **`n_test` or `test_base_rate`** — `chance correction`, `statistical power`
  and `precision floor` all go dark. A random ranker's AP exceeds the base rate
  at finite n, so without these three numbers an AP cannot be placed against
  its own null.
* **`test_average_precision`** — `statistical power` and `precision floor` go
  dark. No exclusion bound can be stated, so a null result excludes nothing.
* **`seed`** — `unit of analysis` and `cross-arm comparison` go dark. Twenty
  records inside one configuration are one configuration observed twenty times,
  and without a seed the tool cannot say which n a p-value rests on.
* **`method`** — `multiplicity` and `cross-arm comparison` go dark.

## Strongly recommended

`schema` returns WARN rather than FAIL, and the named checks skip.

| field | type | what it enables |
| --- | --- | --- |
| `test_label_fingerprint` | str | hash of the test labels **in order**. Without it `pairing integrity` cannot verify a paired test, only assume it, and a silent mismatch is invisible in the summary metrics. |
| `shuffled` | bool | marks a permuted-label control record. Without a control file there is no evidence the pipeline does not leak. |
| `final_converged` | bool | false if the solver hit its iteration cap. `solver health`. |
| `inner_score` | float | the selection score. Without it `selection` cannot show that selection used training folds rather than the reported test score. |
| `params` or `C` | dict/float | the hyperparameters actually selected. `tuning symmetry` compares what each arm had to select from; a method whose selected parameters never vary had nothing to select. |

## Hardware telemetry, strongly recommended

Required only in this sense: **a claim about QPU time, cost or feasibility is
not supported without them**, and `hardware cost claims` states that as an
explicit limitation rather than passing.

| field | type | what it enables |
| --- | --- | --- |
| `provenance` | str | one of `own-hardware`, `borrowed-hardware`, `simulator`, `classical`. **Never inferred.** A record saying `method: "hardware"` with no `provenance` has not told this tool it ran on a QPU, and the report says so. |
| `shots` | int | repetitions per kernel entry. The reason this matters: a pairwise circuit count is not a cost, because hardware runs each circuit once per shot. A cost figure with no shot dimension understates by roughly three orders of magnitude at 1,024 shots. |
| `backend` | str | the machine, e.g. `ibm_kingston`. Makes a timing figure checkable against a real device. |
| `quantum_seconds` | float | metered QPU seconds, as the provider bills them. On IBM Quantum this is `job.metrics()['usage']['quantum_seconds']`. |
| `job_id` | str | optional, and what makes a `quantum_seconds` figure auditable against the provider's own record. |

## Configuration

A *configuration* is a setting the comparison is repeated across: a feature
mapping, a qubit count, a training size. Supply it as top-level fields and let
the audit infer the grouping, or as a nested `cell` dict, or override with
`--cell-fields`.

**The inference rule:** a configuration field varies across records but not
across the methods being compared, so every one of its values is scored by the
same set of methods. That distinguishes `mapping` and `n_qubits`
(configurations) from `embedding` and `reps` (arms of the comparison, since each
of their values is scored by only some methods). The inferred grouping is
always printed, because a wrong grouping silently changes three other answers.

Telemetry is never a configuration. `shots`, `backend`, `quantum_seconds`,
`job_id`, `provenance`, `circuit_evaluations` and the rest are excluded by
name: a cost field taking two values, each scored by every method, would
otherwise be inferred as a configuration and double the cell count.

## Two arms

The comparison usually spans two files. Pass the second with `--compare`.
Without it, **every power and multiplicity figure describes comparisons within
one file**, which is generally not the comparison being tested.

## The friction this format has actually met

On the one external deposit this tool has been run against, **3 of the 7
required fields could be supplied and 4 could not.** The blocker was not the
format. Their endpoint was balanced accuracy, and average precision and ROC-AUC
are different quantities; mapping one onto the other's field name would falsify
a foreign group's results to make this tool look applicable, so the adapter
left them absent and the report said what it could not answer.

That is worth knowing before adopting this. A template does not fix a different
endpoint. If the numbers available to you are balanced accuracy or raw accuracy
only, four of the fifteen checks can speak and eleven cannot, and this tool will
tell you which rather than estimating.
