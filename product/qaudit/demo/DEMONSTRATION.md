# One workflow, demonstrated: retained artefacts to an audit report

Written 26 October 2026. Bounded to one deposit. Everything below is produced by
`reconstruct_kakavand.py` and re-derivable by running it; nothing here was typed
by hand.

    retained artefacts  ->  reconstructed evidence  ->  audit report

## The problem this answers

Kakavand et al. report balanced accuracy. The audit schema wants average
precision and ROC-AUC. `scripts/foreign/kakavand_adapter.py` therefore left four
required fields absent, `schema` returned FAIL, and nine checks reported what
they could not answer. That was the correct output for what the adapter read.

It was not the end of the matter, and the distinction matters commercially:

* **Parsing** recovers a value somebody stored, from a format that is awkward.
* **Recomputation** produces a value nobody stored, from artefacts somebody
  kept.

These four fields needed the second. They are not in the deposit in any format,
and no parser would have found them. What made them reachable is that the group
deposited the 60x60 hardware Gram matrices **and** the labels, and published
their scoring protocol in the same deposit.

## Agreement with the deposit

Re-running their protocol reproduces every reported balanced accuracy exactly.

| experiment | reported BA | recomputed BA | difference | per-fold mean AP | pooled AP |
| --- | --- | --- | --- | --- | --- |
| HW-01 | 0.473214286 | 0.473214286 | 0.0e+00 | 0.8303 | 0.7330 |
| HW-02 | 0.760357143 | 0.760357143 | 0.0e+00 | 0.8425 | 0.8395 |
| HW-03 | 0.549523810 | 0.549523810 | 0.0e+00 | 0.7734 | 0.7458 |
| HW-04 | 0.543809524 | 0.543809524 | 0.0e+00 | 0.7656 | 0.6969 |
| HW-05 | 0.511428571 | 0.511428571 | 0.0e+00 | 0.5012 | 0.4152 |
| HW-06 | 0.537500000 | 0.537500000 | 0.0e+00 | 0.4263 | 0.3736 |

**What this establishes and what it does not.** Six aggregate figures matching to
better than 1e-12 is strong evidence that the protocol, the fold assignment and
the selection rule match. **It does not establish that every implementation
detail matches, and it cannot.** Their `phase3_hardware_runner.py`, which wrote
`result.json`, is not in the deposit; `scripts/audit_hw_results.py` is, and is
what this follows. Fold assignment also depends on scikit-learn's
`StratifiedKFold`, so a future version that changes shuffling would change the
per-fold figures while leaving the aggregate agreement intact or not.

Protocol: nested `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`,
inner selection over C in `[0.01, 0.1, 1.0, 10.0, 100.0]` on mean balanced
accuracy, outer fit at the selected C, `SVC(kernel='precomputed')`.

Dependencies for the run above: Python 3.10.12, numpy 2.2.6,
scikit-learn 1.7.2, on Linux aarch64.

## Per-fold and pooled are different quantities

Both are in `derived_kakavand_hw_provenance.json` and neither is preferred.

**Per-fold** average precision is computed inside one model and then averaged
across folds. Each figure rests on twelve test points.

**Pooled** average precision concatenates `decision_function` values from five
different SVMs, each with its own scale and intercept, so the ranking it scores
mixes incomparable scores. On HW-01 the two read 0.8303 and 0.7330. The gap is
not noise; it is the two quantities disagreeing.

This deposit does not support choosing between them, so the script reports both
with the caveat attached and the audit record carries the per-fold figure, which
is the one that belongs to the split the record describes.

## Class composition, per fold and per dataset

The dataset-level base rate is not the fold base rate, and twelve test points
cannot take an arbitrary rate. Both are recorded on every emitted record.

| experiment | dataset positives | negatives | dataset base rate |
| --- | --- | --- | --- |
| HW-01 | 38 | 22 | 0.633333 |
| HW-02 | 38 | 22 | 0.633333 |
| HW-03 | 32 | 28 | 0.533333 |
| HW-04 | 32 | 28 | 0.533333 |
| HW-05 | 21 | 39 | 0.350000 |
| HW-06 | 21 | 39 | 0.350000 |

| experiment | fold | n_test | pos | neg | fold base rate | chance AP | recomputed AP |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HW-01 | 0 | 12 | 7 | 5 | 0.5833 | 0.6630 | 0.7514 |
| HW-01 | 1 | 12 | 7 | 5 | 0.5833 | 0.6630 | 0.9038 |
| HW-01 | 2 | 12 | 8 | 4 | 0.6667 | 0.7304 | 0.8950 |
| HW-01 | 3 | 12 | 8 | 4 | 0.6667 | 0.7304 | 0.7792 |
| HW-01 | 4 | 12 | 8 | 4 | 0.6667 | 0.7304 | 0.8219 |
| HW-02 | 0 | 12 | 7 | 5 | 0.5833 | 0.6630 | 0.7844 |
| HW-02 | 1 | 12 | 7 | 5 | 0.5833 | 0.6630 | 0.9683 |
| HW-02 | 2 | 12 | 8 | 4 | 0.6667 | 0.7304 | 0.6636 |
| HW-02 | 3 | 12 | 8 | 4 | 0.6667 | 0.7304 | 0.8259 |
| HW-02 | 4 | 12 | 8 | 4 | 0.6667 | 0.7304 | 0.9705 |
| HW-03 | 0 | 12 | 6 | 6 | 0.5000 | 0.5956 | 0.8333 |
| HW-03 | 1 | 12 | 6 | 6 | 0.5000 | 0.5956 | 0.7885 |
| HW-03 | 2 | 12 | 6 | 6 | 0.5000 | 0.5956 | 0.7028 |
| HW-03 | 3 | 12 | 7 | 5 | 0.5833 | 0.6630 | 0.8120 |
| HW-03 | 4 | 12 | 7 | 5 | 0.5833 | 0.6630 | 0.7305 |
| HW-04 | 0 | 12 | 6 | 6 | 0.5000 | 0.5956 | 0.7161 |
| HW-04 | 1 | 12 | 6 | 6 | 0.5000 | 0.5956 | 0.7996 |
| HW-04 | 2 | 12 | 6 | 6 | 0.5000 | 0.5956 | 0.6285 |
| HW-04 | 3 | 12 | 7 | 5 | 0.5833 | 0.6630 | 0.7835 |
| HW-04 | 4 | 12 | 7 | 5 | 0.5833 | 0.6630 | 0.9004 |
| HW-05 | 0 | 12 | 4 | 8 | 0.3333 | 0.4608 | 0.6000 |
| HW-05 | 1 | 12 | 4 | 8 | 0.3333 | 0.4608 | 0.5000 |
| HW-05 | 2 | 12 | 4 | 8 | 0.3333 | 0.4608 | 0.3833 |
| HW-05 | 3 | 12 | 4 | 8 | 0.3333 | 0.4608 | 0.4444 |
| HW-05 | 4 | 12 | 5 | 7 | 0.4167 | 0.5282 | 0.5783 |
| HW-06 | 0 | 12 | 4 | 8 | 0.3333 | 0.4608 | 0.3534 |
| HW-06 | 1 | 12 | 4 | 8 | 0.3333 | 0.4608 | 0.5516 |
| HW-06 | 2 | 12 | 4 | 8 | 0.3333 | 0.4608 | 0.3833 |
| HW-06 | 3 | 12 | 4 | 8 | 0.3333 | 0.4608 | 0.4083 |
| HW-06 | 4 | 12 | 5 | 7 | 0.4167 | 0.5282 | 0.4348 |

**Chance average precision at twelve points runs from 0.4608 to 0.7304.** That
is what a uniformly random ranking scores at these class counts, and several
recomputed figures sit at or below it. **Recovering the metric did not recover an
answer**, and the audit says so: `chance correction` warns that raw average
precision is not comparable across five test-set shapes spanning that range.

## The audit report, before and after

| | deposited records | derived records |
| --- | --- | --- |
| records | 18 | 30 (5 folds x 6 experiments) |
| PASS | 2 | 5 |
| WARN | 2 | 3 |
| FAIL | 1 (schema) | 0 |
| SKIP | 9 | 5 |
| NOT RUN | 1 | 2 |
| questions unanswered | 10 | 7 |

Reconstruction answered three more questions and left seven open. It did not
turn a weak file into a strong one.

    qaudit derived_kakavand_hw.jsonl \
        --cell-fields dataset feature_map k_features n_qubits reducer

## What remains unavailable, exactly

**The permuted-label control is the important missing diagnostic, and it is not
the only leakage-relevant evidence nor proof that leakage is absent.** No run on
scrambled labels was deposited. A valid control cannot be made from the
deposited Gram either: scrambling labels and refitting the same kernel tests
only the classifier, while leakage can enter through the reducer and the feature
selection, which ran before the kernel was computed. A control that covers those
needs the earlier pipeline stages repeated on permuted labels, which needs their
code and their preprocessing, not just their kernel. The audit reports the
absence; it does not report leakage, and nothing here says their pipeline leaks.

**A held-out test set of the kind the schema's one-record-per-split shape
assumes does not exist.** Their design yields five folds of twelve. The schema is
satisfiable, at five records per experiment, and every per-record figure then
rests on twelve points.

**No classical or simulator comparator.** Their ideal and noisy arms need cached
simulator kernels the deposit does not contain, so `cross-arm comparison`,
`statistical power`, `precision floor` and `tuning symmetry` have nothing to pair
and say so.

**Metered QPU seconds.** `hardware_metadata.qpu_seconds` reads 0.0 on all six
runs and the code that wrote it is absent from the deposit, so its meaning is
unresolved. `quantum_seconds` is deliberately not emitted: writing 0.0 would
assert a metered figure nobody has confirmed. The cost check therefore reports
the limitation, which is the correct outcome.

**Wall time does not substitute.** `wall_time_sec` across the six runs spans
569.1 to 4435.2 seconds for an identical workload of 1,830 circuits at 1,024
shots. That variation makes wall time unusable as a QPU-time estimate. **It does
not identify how much of the variation is queueing and how much is other
overhead**, and the deposit contains nothing that would separate them.

## Labelling

Every emitted record carries `derived: true` and a `derivation` block naming the
script, the source experiment, the source seed, the outer fold index, the number
of folds, that sibling folds share one subsample, the endpoint the deposit
actually reported, which endpoints were recomputed here, the recomputed balanced
accuracy, the fold class counts, the fold chance average precision, and the
dataset-level class counts.

Five records from one experiment are **five folds of one subsample and not five
independent experiments.** `unit of analysis` reads the file as 6 configurations
by ~5 seeds and warns that across-configuration claims have n=6, not n=30.

`derived_kakavand_hw_provenance.json` carries the sha256 of every input file,
the protocol, the dependency versions, the 6 assumptions
and the six agreement comparisons.

## Assumptions

1. The protocol is transcribed from scripts/audit_hw_results.py in the deposit: nested StratifiedKFold(5, shuffle=True, random_state=42), inner selection over C in [0.01, 0.1, 1, 10, 100] on mean balanced accuracy, then an outer fit at the selected C. phase3_hardware_runner.py, which wrote result.json, is NOT in the deposit, so this follows the audit script rather than the producing script.
2. Fold assignment depends on scikit-learn's StratifiedKFold implementation. A future scikit-learn that changes shuffling would change the folds and so the per-fold figures. The version used is recorded in this run's provenance block.
3. `seed` in each emitted record is the OUTER FOLD INDEX, 0 to 4, not the experiment's seed. The audit schema defines records sharing a seed as sharing a train/test partition, and under this design the fold is the partition. The real experimental seed, 42, is in the derivation block as `source_seed`.
4. Reproducing six aggregate balanced accuracies is strong evidence that protocol, fold assignment and selection rule match. It does not establish that every implementation detail matches.
5. Only the HARDWARE arm is reconstructable here. Their ideal and noisy arms need cached simulator kernels that the deposit does not contain, so no classical or simulator comparator is emitted and the cross-arm check has nothing to pair.
6. `quantum_seconds` is NOT emitted. The deposit's hardware_metadata carries the field reading 0.0 on all six runs and the code that wrote it is absent, so its meaning is unresolved. Emitting 0.0 would assert a metered figure that nobody has confirmed. The audit's cost check therefore reports the limitation, which is the correct outcome.

## Reproducing this

    export KAKAVAND_DEPOSIT=~/Documents/foreign-audit/extracted/QSVM-Benchmark-Paper
    python product/qaudit/demo/reconstruct_kakavand.py \
        --out derived_kakavand_hw.jsonl \
        --summary derived_kakavand_hw_provenance.json
    qaudit derived_kakavand_hw.jsonl \
        --cell-fields dataset feature_map k_features n_qubits reducer

The script exits non-zero if any reported balanced accuracy fails to reproduce,
so a silent divergence is not possible. The deposit is not redistributed here;
it is CC BY 4.0 and available at Zenodo 10.5281/zenodo.19197916.
