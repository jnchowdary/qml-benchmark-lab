# qaudit

Reads a benchmark results file and reports **what that file can and cannot
establish**. It does not say which model won, and it is not a defect detector.
The limits are in "What this does not do" below, which is the part to read
first.

Extracted from the QML Benchmark Lab research repository. The fourteen checks
and their wording are unchanged from that repository's `scripts/audit.py`;
`EXTRACTION.md` records what moved, what did not, and the two divergences the
extraction found. One check has been added since.

## Install and run

    pip install .
    qaudit RESULTS.jsonl

numpy and scipy are the only dependencies. The research repository this came out
of pins qiskit, qiskit-machine-learning, qiskit-aer, pennylane,
pennylane-lightning, scikit-learn, pandas, statsmodels, matplotlib and joblib.
No check here reaches any of them.

Exit code is 0 when everything passed or skipped, 1 on any warning, 2 on any
failure.

## Start here

* **`EXAMPLE_REPORT.md`** — the complete output on a published deposit this
  tool had no part in producing, with what the mapping cost. Read it before
  anything else.
* **`FIELDS.md`** — every field, what it enables, and which checks go dark
  without it.
* **`template.jsonl`** — three records in the right shape: a hardware quantum
  arm, its classical comparator on the same split, the same setting simulated.
* **`EXTRACTION.md`** — how this package was taken out of the research
  repository and how that was verified.

## Four things a report keeps apart

A report states these separately, because they vary independently and merging
them lets a reader infer one from another:

1. **Where the data came from** — declared per record in `provenance`, one of
   `own-hardware`, `borrowed-hardware`, `simulator`, `classical`. **Never
   inferred.** A record saying `method: "hardware"` with no `provenance` field
   has not told this tool a QPU ran, and the report says so.
2. **Whether each check could run** — `PASS`, `WARN`, `FAIL`, `SKIP`,
   `NOT RUN`. A `SKIP` is missing evidence, not a passed check, and the summary
   counts unanswered questions separately so it cannot read as one.
3. **What it found** — the detail line and the numbers behind it.
4. **What validates that check** — one external case exists, and the report
   names the checks nothing external has ever exercised.

Every report also records the invocation that produced it and the numeric
environment it ran in. Both exist because extracting this package found that
the research repository's own committed report could not reproduce itself.

## What this does not do

Taken from section 5.6 of the paper this came out of, because the limits are
documented and should not have to be rediscovered:

- **Every check was written after the defect it catches**, in the project that
  wrote it. A list of caught mistakes is evidence that one project eventually
  noticed its own, not that this tool catches a stranger's.
- **On the only occasion these checks met foreign records they found no
  defect, and were not looking for one.** The output was one measurement, one
  report of missing fields, nine refusals and one not-run.
- It cannot see analysis performed outside the file it is given, a wrong kernel
  implementation, a mis-specified feature map, or a dataset leaking labels
  through preprocessing.
- It does not settle whether a quantum kernel is better. The Tier 2 hook widens
  what it can see and does not change that.
- A clean report means the file supports the kind of claim being made. It does
  not mean the claim is true.

No comparison with other tools is claimed anywhere here, because none has been
done.
