# QML Benchmark Lab: Week 6 Record

Written 29 September 2026. Covers work done 27 to 29 September 2026.
376 tests passing, 73 of them in `tests/test_audit.py`.

**No deviation record was opened.** One should have been and was not: the
pre-registration's section 1 rewrite has now been deferred for three weeks
running and is named again in section 10.

---

## 1. What week 6 was for

The protocol's README claims it "runs against any pipeline that can emit a
documented record format". Until this week it had only ever been run against the
pipeline that wrote it, and every check in it was written after a specific
failure in that same pipeline. The generality claim is the load-bearing claim of
the whole artefact and it had no evidence behind it.

The week was chosen to fix that: audit a foreign pipeline, with the authors told
first. It did fix it, in section 5. Sections 2 and 3 are what happened on the
way and cost more than the objective did.

---

## 2. Six of seven published claims about a named third party were wrong

`docs/audit-protocol.md` section 1 and `docs/week-04-report.md` section 15 both
asserted that Kakavand, Strohmeyer & Schlotter (2026) omit a list of checks.
Those claims were written from their manuscript. Their reproducibility deposit
(Zenodo 10.5281/zenodo.19197916, CC BY 4.0) was public and linked from the
abstract page on the day the claims were written. It was read on 27 September.

| claim | verdict | evidence |
| --- | --- | --- |
| no multiplicity correction across 29 comparisons | **false** | `phase1_statistical_analysis.py` applies Benjamini-Hochberg **and** Bonferroni; `significant_005_bh` is the decision column |
| features enter the circuits without rescaling | **false** | `preprocess/pipelines.py` offers `StandardScaler` and `MinMaxScaler(0,1)`, fit on train only |
| no shuffled-label controls | true but misleading | no label permutation, but an exact paired permutation test is always computed and `validate_leakage_free.py` addresses leakage directly |
| no chance-corrected metric | **category error** | their endpoint is balanced accuracy, chance 0.5 by construction. Criticised for not fixing a problem their metric does not have |
| no numerical conditioning floor | **overstated** | `diagnostics/kernel_analysis.py` computes condition number, minimum eigenvalue, effective rank and the eigenspectrum |
| no geometric difference | true, neutral | |
| no fitted classical surrogate | **true** | their `margin_surrogate` is an SVM-margin proxy. The only claim that survived |

Two further findings make the original paragraph worse than merely inaccurate.
Their `svm_C_range` is defined once and shared by every arm, so classical and
quantum get one hyperparameter grid: the symmetry whose absence was **this
project's** largest defect, recorded in D4. And their exact permutation fallback
exists because they reasoned about the Wilcoxon two-sided p-floor of 2/2^n at
small n, which is D2's instinct applied to the test rather than to the pipeline.

Both documents were corrected and pushed at `6940bb4` before any contact was
made. The week-4 report is a record, so it carries an appended correction rather
than an edited line.

**A second target is half-checked.** The same section asserts of Flórez-Ablan,
Roth & Schnabel (2025) that they use "no average precision, no chance-level
correction, no negative controls". Their manuscript was read on 28 September:
the negative-control claim holds, and the other two are the same category error,
because they report ROC-AUC, whose chance level is also 0.5 by construction.
They also have public code that has not been read. That is the same one-click
distance the Kakavand claims were at, and it is still open.

---

## 3. What this costs: the positioning, not the protocol

The claims in section 2 supported a position: that existing benchmarks do not
perform these checks, and that the gap the protocol addresses "is not another
comparison". That position does not hold. Published work in this area is
statistically careful, and Kakavand et al.'s practice at publication was ahead of
this project's at the end of week 4.

What holds is narrower and is now what section 1 of the protocol says: decision
rules rather than diagnostics — a measured reproducibility floor, classical
surrogate equivalence in endpoint units, shuffled-label controls adjudicated
against both a sigma bar and that floor, cross-arm rather than within-arm power
— plus a record format and a portable tool that make checking cheap for a
reader. That is a real contribution. It is not "nobody else is careful".

**New rule, effective immediately.** A claim in this project about what another
group did not do must cite their code or their data, or it is not made.

---

## 4. An independent result, and someone else got there first again

A literature check on 28 September found Tekeli (arXiv:2608.29422, 29 August
2026, unpublished, single author, with a Zenodo deposit). He derives in closed
form that the ZZ feature map's kernel at small bandwidth is a Gaussian with
metric M = I + pi^2 Q, Q the signless Laplacian of the entanglement graph. His
**Proposition 2** states that under the unshifted phase convention -- the IQP
convention -- the metric collapses to the identity and the kernel is an
*isotropic* Gaussian **regardless of entanglement**, with error O(s^4).

That is a quantitative prediction about kernels this project already had on
disk. `scripts/tekeli_check.py` sweeps bandwidth, fits the nearest isotropic
RBF with no labels, and tests whether gamma scales as b^2. The angle family is
the positive control, because week 4 derived gamma = (reps*b)^2/4 and confirmed
it on real data.

| setting | coefficient c in gamma = c*b^2 | predicted | flat to |
| --- | --- | --- | --- |
| angle-r1 (control) | 0.2503 | 0.2500 | b = 0.281 |
| angle-r2 (control) | 1.0005 | 1.0000 | b = 0.097 |
| iqp-r1 | **0.2502** | none | b = 0.012 |
| iqp-r2 | **0.2502** | none | b = 0.012 |

Exponent 2.00 in every case; both controls land at 0.1% and 0.0%.

**The entangling circuit's classical limit carries the same coefficient as the
separable one**, agreeing to four significant figures across six bandwidths
before the higher-order terms separate them. Entanglement contributes nothing to
the leading term. That is Proposition 2, confirmed on different data, in
classification rather than regression, by a fitted surrogate rather than a
derived one. What entanglement costs is range: IQP leaves the quadratic regime
24x earlier than angle in the same pipeline.

A second result qualifies week 4. **IQP's coefficient does not depend on `reps`
and angle's does** (0.25 and 1.00, following reps^2/4). PennyLane's
`IQPEmbedding(n_repeats=)` is not the disguised bandwidth knob that stacking
`AngleEmbedding` is.

Committed at `992874b`. Exploratory under D4: three seeds, one dataset, one cell.

---

## 5. The protocol met a foreign pipeline

`scripts/foreign/kakavand_adapter.py` reads their six hardware experiments as
audit records and serves as a `--hook`. It renames nothing: their endpoint is
balanced accuracy, the schema wants average precision and ROC-AUC, and mapping
one onto the other's field name to make the tool appear applicable would be
falsifying a foreign group's results.

The run produced **one measurement and eight precise refusals.**

**The measurement.** Kernel conditioning, over all six deposited Gram matrices,
measured on `ibm_fez` at 1024 shots: worst condition number **4.5e+05**. This
project's own kernels run 7.8e+19 on churn registered to 1.1e+33 on fraud —
fourteen to twenty-seven orders of magnitude worse. At n = 60 on three to five
qubits, with shot noise lifting the near-zero eigenvalues, their dual is well
determined and D2's precision floor would not be needed at all. That is the
first cross-pipeline comparison this project has been able to make.

On a partial sample of two of the six the same check read 1.7e+04, understating
the worst case by a factor of 26. It was visible only because the check prints
how many kernels it sampled.

**The refusals**, which are the more useful half. Four required fields are
absent, so chance correction, power and the precision floor say which. There is
no classical arm in the hardware phase, so cross-arm has nothing to compare. One
seed, so unit-of-analysis warns and power cannot speak. No `inner_score`, so
selection cannot be shown. None of this is a criticism of their work: it is a
map of what a reader can and cannot verify from that deposit, produced in
seconds, which is the entire argument for the record format.

**One thing their schema does better than ours did.** They record
`subsample_indices` — exactly which 60 rows were used. It is not a label
fingerprint, but it identifies the split precisely, and it solved independently
the problem this project only solved when a fingerprint field was added in
week 3.

---

## 6. Eight defects, all in this project's analysis code

Six in `scripts/tekeli_check.py`, found in four successive runs; two in
`scripts/audit.py`, found by the foreign audit. None was in any record.

1. **An exponent fitted through two points.** The plateau detector cut at the
   second bandwidth, so a slope was computed from two distinct x-values — exact
   by construction, reporting `R2 1.00000` and a standard error of `0.000` for
   all four settings at once.
2. **A plateau anchored on its worst-determined point.** The detector took the
   ratio at the smallest bandwidth as its reference, which is precisely where
   the kernel is closest to the identity and the fit is least determined.
3. **Grid quantisation read as physics.** `fit_gamma` searches a fixed 121-point
   log grid of step 1.1220. Consecutive fitted gammas landed exactly six steps
   apart where the true ratio is 5.77 steps, inflating the exponent from 2.000
   to 2.080. `fit_gamma` was deliberately left alone — every surrogate figure
   already committed came from it — and the refinement lives in the new script.
4. **A tolerance loose enough to call a drift flat.** The 5% default admitted a
   monotone 7% climb in the IQP rows and reported it as a plateau. The control
   holds its ratio to 0.1%, so 5% was never the right order.
5. **A refinement clamped at the grid floor.** `FIT_GAMMAS` bottoms out at 1e-05
   and a bounded refinement around that seed could reach no lower than 2.73e-06.
   Two bandwidths reported the identical clamped value.
6. **Seed agreement that was a clamp.** The seed-spread column read 0.0% on
   those rows because all three seeds hit the same stop. Agreement between seeds
   is not evidence of correctness when every seed is pinned against a limit.
7. **Checks crashing instead of refusing.** On the foreign file three checks
   reported `check raised KeyError('n_test')` as a FAIL. Unanswerable is not
   failed, and `check_schema` had already named every absent field one line
   above. Checks now declare the fields they need and SKIP naming them.
8. **A schema failure that invalidated a valid measurement.** The FAIL read
   "Nothing below can be trusted" directly above the kernel-conditioning reading
   — the only measurement that report contained, and one needing none of the
   absent fields.

The pattern across all eight, and across the seven of week 5: **a detector or a
fitter quietly substituting its own limits for the measurement.** Not one was
caught by a test. Every one was caught by a positive control with a known
answer sitting alongside the thing being measured, or by reading a report on
real data.

---

## 7. Four wrong readings of my own

Separate from the code, because the code was fixed and these were not caught by
fixing anything.

1. **D6's bandwidth row was declared not to reproduce.** It reproduces exactly;
   the checker was comparing it against the wrong one of three power quantities.
2. **D6's primary-cell row was declared an arm-level figure mislabelled.** It is
   not. The inference came from two numbers coinciding to four decimal places —
   a coincidence D6's own correction note documents in writing, in a passage
   that had been read and quoted from in the same session.
3. **The IQP classical limit was read wrong twice in succession**: first as a
   sharp boundary at 0.054 to 0.0755 bracketing Tekeli's 0.072, then as an
   absence of any flat regime at all. Both were artefacts of the detectors in
   section 6. The third reading, after the detectors were fixed, is section 4.
4. **"Rewrite the pre-registration's section 1" was proposed four times** as the
   next major task, and as the thing blocking OSF. The pre-registration is never
   edited -- D6 states it in terms -- so the proposal contradicted the discipline
   this project exists to demonstrate, and nothing was blocking OSF in any case.
   Four weeks of "next week's spine" pointed at a task that should not be done,
   while two registered confirmatory hypotheses sat unexecuted and unmentioned.

---

## 8. Tests and housekeeping

376 tests, up from 373. `tests/test_audit.py` grew from 70 to 73. Every defect
in section 6 has a regression test built from the case that exposed it, including
one pinning that the skip-on-missing-field guard did not become a blanket
exception swallow.

`src/qbench` was not touched this week. Every change is in `scripts/` and
`docs/`, so no experimental result is affected by any of it.

A transfer to the local machine silently delivered an earlier version of a file
under a reused filename. It was caught because every transfer in this project is
staged back and diffed before being reported as landed. That practice exists
because of an identical failure in week 5.

---

## 9. Decisions taken this week

* **Claims about other groups must cite their code or data.** Section 3.
* **The protocol's positioning is what it adds, not what others lack.**
* **An adapter never renames a foreign field to fit our schema.** An absent field
  is reported absent.
* **A check that lacks a field it needs SKIPs and names the field.** A check that
  is genuinely broken still fails loudly.
* **Contact before publication.** All three Kakavand authors were written to on
  27 September, after the corrections were public, leading with the correction
  rather than with a request.

---

## 10. Still open

* **H2 and H3 have never been tested.** Section 2 of the pre-registration
  registers three confirmatory hypotheses and says of the second: "H2 is the
  reason this project exists." H1 was tested in week 4. H2 and H3 were not, D5
  specified how and has been in force since 25 September, and the computation
  was never run. Week-4 section 14 says exactly what to do. The project turned
  toward the protocol and did not come back. **Two of three registered
  confirmatory tests are unexecuted**, and this is the largest open item in the
  project by a wide margin. It is week 7's spine.
* **A live result is waiting inside it.** Week-4 section 9, on eight seeds: at
  every lambda, g is larger at the registered bandwidth than at the selected
  one, and the registered bandwidth is where the quantum kernel performed
  *worse*. g was highest exactly where the kernel did least well, the opposite
  of what Huang et al. predict. If that survives all 360 units it is a
  substantive negative result about the geometric difference as a pre-training
  screen -- and unlike everything else this project has produced recently it
  would be **confirmatory**, because it was registered before the data existed.
* **The Flórez-Ablan code check.** Leaving one third party corrected and another
  flagged-but-unchecked is worse than doing both or neither.
* **OSF registration is not blocked by anything.** It was recorded through this
  week as waiting on a rewrite of the pre-registration's section 1. That was
  wrong twice over. v1.0 plus D1 to D6 can be registered exactly as they stand;
  git already timestamps the document publicly from 24 September and OSF adds an
  independent immutable record and a DOI, requiring no edit to anything.
* **The exponent field prints `± 0.000`**, hiding whether the standard error is
  1e-4 or 1e-7. After this week a reader of this repository has specific reason
  to distrust that.
* **Four times the seeds on churn's tuned arm**, to resolve point estimates of
  0.003 to 0.005 against an MDE of 0.008. Compute, not code.
* **Grid adequacy against a shuffled null**, the last genuinely unrunnable check.
* **The history-rewrite backup** can be deleted.

---

## 11. What this week says about the project

Week 4's lesson was that a literature search is not optional. Week 5's was that a
green test suite is not evidence that a measurement tool measures anything.
Week 6's is narrower and worse: **this project published six wrong claims about
a named third party, from a reading of their paper, while their code sat one
click away.**

That happened in a document whose entire subject is the difference between
asserting and measuring. The rule in section 3 is the fix, and the fact that it
had to be written down is the finding.

The consolation is structural rather than moral. The protocol's first foreign
run produced one measurement, eight accurate refusals and two defects in itself.
That is what it is supposed to do, and it is a better argument for the record
format than the paragraph it replaced ever was.

**A second thing this week says, found on its last day.** While all of the above
was happening, two of the project's three registered confirmatory hypotheses had
never been run, and no weekly record had said so. The attention went to the
protocol, to correcting claims about other people's work, and to a task that
should not have been done at all. A pre-registration is worth nothing if the
tests it registers are not executed, and this one has been sitting half-executed
since week 4 while five weeks of records discussed everything else.
