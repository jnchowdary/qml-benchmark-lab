# Extracting the audit: what moved, what did not, and two divergences

Written 25 October 2026. Amended 26 October 2026.

The claim this document supported was narrow and checkable: **`qaudit` gives the
same report as `scripts/audit.py` on the same input.** `verify_extraction.py`
checks it on every run and is the thing to trust.

**That claim has since narrowed and the narrowing is stated here rather than
left to a reader to discover.** The package has diverged from the research copy:
158 net lines across 14 hunks, being one added check, one verdict change in
`schema`, and two corrected PASS messages. See VALIDATION_NOTES.md for each.
What `verify_extraction.py` still establishes is **agreement with the research
repository's own committed report on the one external file**, field for field,
exactly. That is agreement on that file. It is not a guarantee of agreement
across all inputs, and the `schema` change is an example: on the Kakavand
records `schema` FAILs on required fields before it ever reaches the
recommended-field list, so the regression does not exercise the behaviour that
changed.

**The research copy is not being edited to match.** `scripts/audit.py` is what
produced the results in the closed paper, and §5.6 describes it as it stands. It
remains the record of what generated the published figures; the package is the
forward copy.

Below records what the first runs found.

## What was copied, and how little was changed

| origin | destination | change |
| --- | --- | --- |
| `src/qbench/stats.py` | `src/qaudit/_qbench_stats.py` | none, byte-identical |
| `src/qbench/metrics.py` | `src/qaudit/_qbench_metrics.py` | none, byte-identical |
| `scripts/audit.py` | `src/qaudit/audit.py` | 7-line import block **at extraction**; has since diverged, see the amendment above |
| `tests/test_audit.py` | `tests/test_audit.py` | 5-line import block |

`EXTRACTION_SOURCES.tsv` carries each origin's sha256. The two statistics
modules are copied whole rather than having their two needed functions sliced
out, so that no judgement of mine sits between the research code and the
packaged code. Neither module references anything else in `qbench`.

**What the extraction removed is the dependency list, not the code.** The
research repository's `requirements.txt` pins qiskit, qiskit-machine-learning,
qiskit-aer, pennylane, pennylane-lightning, scikit-learn, pandas, statsmodels,
matplotlib and joblib. No check reaches any of them. `qaudit` requires numpy
and scipy, and installs and runs in an environment containing nothing else.

## A correction to an earlier claim of mine

I said the extraction carried a safety net of 115 test functions, from
`tests/test_audit.py` and `tests/test_audit_fixes.py`. **That was wrong, by 39.**
`test_audit_fixes.py` is a project-wide regression file: it imports
`qbench.data`, `qbench.features`, `qbench.kernels.classical`, `qbench.tuning`,
pennylane and scikit-learn, and tests `power_analysis`, `check_grid_edges` and
`adjudicate_grid`. Essentially none of it tests the audit. The portable net is
`test_audit.py`'s **76** functions, which pass unchanged.

It is the same shape as the mutation harness flattering its own coverage, which
section 5.6 collects: a count asserted from two filenames rather than from the
imports. It was stated in conversation and not published, and it is corrected
here rather than left.

## Divergence 1 — the sample size, and a report that cannot reproduce itself

The first comparison diverged on one check of fourteen.

    committed   worst 4.5e+05 over 6 sampled kernels
    extracted   worst 1.7e+04 over 2 sampled kernels

**Cause: `--hook-sample` defaults to 6**, which on this file reaches two of the
six deposited Grams. 1.7e+04 is the exact reading section 5.6 already records
as understating the worst case by a factor of 26. At `--hook-sample 18` the
committed report reproduces exactly. Nothing about the extraction is involved.

**The finding is that the committed report does not record the sample that
produced it.** `results/audits/kakavand_hw_report.json` stores `file`,
`control` and `floor`. It does not store `cell_fields`, `hook` or
`hook_sample`. So the one parameter that moves the only Tier 2 measurement in
the paper by 26 times is absent from the artefact carrying that measurement,
and the default returns the understated reading silently.

This does not change section 5.6's count of eight public repairs. The number
4.5e+05 is correct and correctly reported, and no verdict rests on the
omission. It sharpens the Tier 2 item already in that section, which says a
`--hook-sample` reading should be treated as a prompt to run the full analysis:
a reader of the committed report cannot tell which they are holding.

**What this requires of `qaudit`:** a report records the invocation that
produced it. Not as a convenience. A report that cannot reproduce itself is not
evidence of anything.

## Divergence 2 — the last digits of a condition number, which were never determined

At the reproducing sample every status, every detail string and every integer
agreed. Two floats did not.

    cond_min   committed 10.565166570822727    here 10.565166570822726
    cond_max   committed 453631.34235576633    here 453631.34235548635

**Cause: the floating-point environment, not the port.** The committed report
was produced on macOS arm64 with numpy 2.4.4 and scipy 1.17.1; this check ran
on aarch64 Linux with numpy 2.2.6, scipy 1.15.3 and scipy-openblas.

The evidence that the digits carry nothing is internal to one environment.
Three mathematically identical routes to HW-02's condition number, computed
side by side in the same process, disagree:

    np.linalg.cond        453631.3423554864
    max(s) / min(s)       453631.3423554864
    eigvalsh magnitudes   453631.3423575828   spread 4.62e-12 relative

The gap between the two environments is **6.17e-13**, smaller than the 4.62e-12
spread between equivalent algorithms on one machine. Both readings print as
`4.5e+05`, which is what the report states and what any conclusion uses.

**Confirmed, and the cause narrowed.** Run on macOS arm64, the platform that
produced the committed report, the comparison passes with **no tolerance at
all** -- every float bit for bit -- under numpy 2.5.4 and scipy 1.18.1, where
the committed report was produced under numpy 2.4.4 and scipy 1.17.1. Two
library versions on one platform agree exactly; one platform change does not.
The variable is the BLAS, not the library version.

**So the comparison is exact by default**, and `--rtol` is the opt-in for
comparing a report across platforms. The earlier 1e-9 default was a workaround
for the machine the first check ran on rather than a property of the
measurement, and a tolerance whose purpose is to make one environment pass is
the kind of threshold this protocol exists to refuse. What 1e-9 would fail to
catch is a genuine change to a condition number smaller than one part in a
billion; the conditioning check's threshold is 1e12 against readings of 1e+01
to 1e+05, so a change at that resolution cannot move a verdict. That makes the
tolerance safe when it is needed and is not a reason to apply it by default.

**What was deliberately not done.** The stored floats were not rounded and
`audit.py`'s output was not changed. Preserving behaviour was the instruction,
and a report whose numbers silently gained a precision floor would no longer be
comparable with the one committed in September.

**What this requires of `qaudit`:** a report records its numeric environment,
so a reader can tell a platform difference from a real one. Deviation D2 of the
research project is about exactly this, a reproducibility floor in average
precision, and the report it produces has no precision floor on its own stored
numbers. Added as a top-level key, which leaves every existing field untouched.

## Verification status

* 76 of 76 ported tests pass, in an environment of numpy, scipy and pytest.
* All 14 checks reproduce the committed foreign report at `--hook-sample 18`,
  field for field, **exactly, with no tolerance**, on macOS arm64 under numpy
  2.5.4 and scipy 1.18.1.
* The same comparison on aarch64 Linux under numpy 2.2.6 and scipy 1.15.3
  needs `--rtol 1e-9`, and the largest divergence is 6.17e-13.
* Exit code 2 on a FAIL, as before.
* Everything asserted in this document is re-checked by
  `verify_extraction.py` on every run, which is now the regression guard for
  every change made to this package after the extraction.

## Two defects found after the extraction, by running the template

Neither was caused by the extraction. Neither appears on the one external file,
which fails on required fields and never reaches either code path. Both were
found by running the tool on its own shipped template, which is the argument for
shipping one that is exercised rather than described.

**`check_schema` warned about an absence the protocol permits.** `cell` was in
its recommended-fields list, while section 2 of the protocol says configuration
may be supplied *either* as a nested `cell` dict *or* as top-level fields the
audit infers. The template takes the documented second route and was warned for
it. The check now warns only when a file has neither route, and names both.

**`check_negative_control` printed a sigma with no meaning.** Its verdict rule
has always required both a sigma bar and the reproducibility floor, because the
first version of it divided by a standard error of order 1e-22 and reported
3.5e+16 sigma on a mean deviation of 0.000014. The PASS line printed the sigma
regardless, and the template's first run read
`normAP -0.0000 (-479279874081.53 sigma)`.

That is the common case and not the edge case: a control sitting at its null has
almost no spread across splits by construction, so a healthy control is exactly
when the figure is residue. The PASS line now prints the deviation, says it is
inside the floor of its stated null, and says why no sigma is given. The verdict
logic is untouched and a real leak still FAILs, with a test for it.

**What the template's own first draft got wrong**, recorded because it is the
same class of error the tool exists to report. The selected hyperparameters were
encoded into the method name, which gave five methods, so no configuration field
was scored by the same set of methods, the inference found nothing, and every
quantum parameter looked fixed to the tuning check. And the control's labels
were permuted on average precision while ROC-AUC kept its real values, which the
negative control correctly caught at +45 sigma on the endpoint that had not been
permuted. Both are now asserted against the shipped files by
`tests/test_check_fixes.py`, so the template cannot rot into either again.

After these changes: **116 tests pass as of 26 October 2026**, and the external
report still reproduces field for field. The count is dated deliberately: an
undated figure in a document goes quietly wrong, which is the failure recorded
at the end of VALIDATION_NOTES.md.
