# A worked example, end to end, on the one real external file

What follows is the complete output of this tool on a published reproducibility
deposit it had no part in producing. It is reproduced here because the honest
case for this tool is the shape of this report, and a prospective user should
see it before being told anything about it.

**Read the report first.** The commentary is after it.

## The input, and what reading it cost

The subject is the hardware phase of Kakavand, Strohmeyer & Schlotter (2026),
arXiv:2604.18837, deposited at Zenodo 10.5281/zenodo.19197916 under CC BY 4.0:
six IBM `ibm_fez` runs, their measured 60x60 Gram matrices kept because they
cannot be regenerated without buying QPU time again, and 18 records across
three arms.

Getting it into this format took **171 lines of adapter**, in
`scripts/foreign/kakavand_adapter.py` of the research repository. What that
bought, and what it did not:

| | supplied | absent |
| --- | --- | --- |
| required fields (7) | `method`, `seed`, `n_train` | `n_test`, `test_base_rate`, `test_average_precision`, `test_roc_auc` |
| recommended fields (5) | `final_converged` | `test_label_fingerprint`, `shuffled`, `inner_score`, `params` |
| hardware telemetry (4) | `shots` | `provenance`, `backend`, `quantum_seconds` |

**Four of the seven required fields were not a formatting problem.** Their
endpoint is balanced accuracy. Average precision and ROC-AUC are different
quantities, and writing one into the other's field name would falsify a foreign
group's results to make this tool look applicable. The adapter left them
absent. The report below is what that produces, and it is the result of the
exercise rather than a degraded version of one.

They did one thing this format does not ask for and it is worth naming: they
recorded `subsample_indices`, which 60 rows of the source dataset were used.
That is not a label fingerprint, but it identifies the split exactly. A foreign
schema solved the same problem a different way.

## The report

```

AUDIT: results/audits/kakavand_hw.jsonl
This audits METHOD, not results. It never says which model won.
  Configuration grouped by: dataset, experiment_id, feature_map, k_features, n_qubits, reducer, split_fingerprint (inferred from the data). Override with --cell-fields if that is wrong.

  WHERE THIS DATA CAME FROM, as the file itself declares it:
    No record declares `provenance`, so this file does not state whether any number came from a QPU, a simulator or a classical model.
    cost telemetry present: shots on 18 of 18, backend on 0 of 18, quantum_seconds on 0 of 18

  [ FAIL  ] schema                           required fields missing from some records: n_test, test_base_rate, test_average_precision, test_roc_auc. Discount the checks that name them below; the checks that do not need them still answer.
  [ SKIP  ] chance correction                records do not carry n_test, test_base_rate, so this question cannot be answered from this file. That is a property of the records, not a failure of the check.
  [ SKIP  ] negative control                 no permuted-label control supplied (--control). Without one there is no evidence the pipeline does not leak.
  [ SKIP  ] pairing integrity                no test_label_fingerprint. Paired tests across methods cannot be verified, only assumed, and a silent mismatch is invisible.
  [ PASS  ] solver health                    all 18 final fits converged.
  [ WARN  ] unit of analysis                 18 records = 6 configurations x ~1 seeds. Across-configuration claims have n=6, not n=18. State which n any reported p-value rests on.
  [ SKIP  ] statistical power                records do not carry test_average_precision, n_test, test_base_rate, so this question cannot be answered from this file. That is a property of the records, not a failure of the check.
  [ SKIP  ] precision floor                  records do not carry test_average_precision, n_test, test_base_rate, so this question cannot be answered from this file. That is a property of the records, not a failure of the check.
  [ WARN  ] multiplicity                     this file supports 18 pairwise comparisons across 6 configurations. Uncorrected, the chance of at least one spurious rejection at alpha 0.05 is about 0.60. Declare which are confirmatory, or correct (Bonferroni would be 2.78e-03).
  [ SKIP  ] tuning symmetry                  no `params` or `C` field, so it cannot be seen whether each method had hyperparameters to select.
  [ SKIP  ] cross-arm comparison             only one arm supplied. Every figure above describes comparisons WITHIN this file. If the claim being made is against another arm, pass it with --compare or the power and multiplicity numbers describe the wrong comparison.
  [ PASS  ] kernel conditioning              condition number stays below 1e12 (worst 4.5e+05 over 6 sampled kernels covering 1 method(s) (hardware) on 1 seed(s)), so the dual is well determined.
  [NOT RUN] classical surrogate equivalence  needs training_data, refit in --hook. Fits the nearest classical kernel with no labels and runs it through your pipeline on your split; a kernel that scores what its surrogate scores is that surrogate.
  [ SKIP  ] selection                        no inner_score field, so it cannot be shown that model selection used training folds rather than the test score.
  [ SKIP  ] hardware cost claims             no record declares `provenance`, so this file does not state that any number came from a QPU and no QPU-cost claim is in scope. Present anyway: shots on 18 of 18, backend on 0 of 18, quantum_seconds on 0 of 18. Declare `provenance` (see FIELDS.md) if a hardware claim is being made.

  Not runnable from records alone:
  [NOT RUN] grid adequacy against a shuffled null
            needs a re-run, not a hook: the same pipeline on permuted labels with a widened grid. Widening raises the best inner score even when nothing is better, so hyperparameter edge flags never justify it on their own.

  WHAT VALIDATES THESE CHECKS
    Every check here was written after the defect it catches, in the project that wrote it. One external case exists: Kakavand et al.'s hardware deposit, audited 29 September 2026. It produced four readings, one report of missing fields, eight refusals and one not-run, and it found no defect in the pipeline it audited. It was not looking for one. A list of caught mistakes is evidence that one project eventually noticed its own, not that this tool catches a stranger's.

    On that one file: 4 checks produced a reading, 8 declined and named what they could not answer.
    Never exercised on any external file: hardware cost claims.

  2 passed, 2 warnings, 1 failed, 9 skipped for missing fields.
  10 question(s) were NOT ANSWERED. A SKIP is missing evidence, not a passed check, and nothing above should be read as this file having satisfied those checks.
  A FAIL means a conclusion drawn from this file is not supported BY this file. It does not mean the conclusion is wrong.
```

## What this establishes, and what it does not

**It establishes one measurement.** Kernel conditioning across all six
deposited Grams, worst 4.5e+05, which is below the 1e12 at which an SVM dual
becomes underdetermined. So the dual is well determined and rank statistics on
these kernels are usable.

**It establishes nine things a reader cannot verify from that deposit**, each
naming the field whose absence blocks it: chance correction, statistical power,
the precision floor, pairing integrity, selection, tuning symmetry, the
negative control, the cross-arm comparison and any QPU-cost claim. Before this
run, a reader could not have said which of those questions the deposit could
answer. After it, they can, in seconds, without the originating pipeline.

**It found no defect in their work and was not looking for one.** Nothing here
is a criticism of that paper. It is a map of what a reader can and cannot
verify from what was deposited.

**The criterion by which this counts as useful, stated rather than assumed.**
The output is useful if it changes what a reader knows about the deposit's
evidential reach. That criterion is met. It is a claim about a reader's state of
knowledge and not about the quality of the audited work, and it does not
generalise to defect detection, because on the only occasion these checks met
foreign records they detected none.

## The friction, for anyone deciding whether to adopt this

This is the number to weigh. The deposit above was made by researchers who
**wanted** their work reproducible and published it openly, and 4 of 7 required
fields were still unavailable. A vendor supplying numbers under a
non-disclosure agreement will supply less, not more.

So the question for a technical evaluator is not whether this report is useful.
It is whether the party making the claim will hand over `n_test`,
`test_base_rate`, an average precision, a label fingerprint and an inner
selection score. If they will, 15 checks can speak. If all that exists is a
balanced accuracy in a slide, 4 can, and this tool will say which 4 rather than
estimating the rest.

`FIELDS.md` lists every field, what each one enables, and what goes dark
without it. `template.jsonl` and `template_control.jsonl` are a complete input
in the right shape, eight records across two configurations, two seeds and two
arms with a permuted-label companion. Running them puts twelve of the fifteen
checks on the record, which is the contrast worth seeing beside the four above.

## Regenerating this

```
export KAKAVAND_DEPOSIT=~/Documents/foreign-audit/extracted/QSVM-Benchmark-Paper
qaudit results/audits/kakavand_hw.jsonl \
    --hook scripts/foreign/kakavand_adapter.py \
    --hook-sample 18 \
    --json example_report.json
```

Exit code 2, because one check FAILs. The `--hook-sample 18` matters and the
JSON now records it: at the tool's default of 6 the conditioning check reaches
two of the six Grams and reads 4.5e+05 as 1.7e+04. The research repository's own
committed report of this run does not record which sample produced it, which is
how that gap was found. See `EXTRACTION.md`.

The `environment` block in the JSON names the Python, numpy, scipy and BLAS that
produced the numbers, because two condition numbers in this tool's regression
differ in their last digits between platforms while agreeing across library
versions. The transcript above was produced on Linux aarch64; regenerating it on
another machine will change that block and may change those digits, and will
change nothing a conclusion rests on.
