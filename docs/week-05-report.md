# QML Benchmark Lab: Week 5 Record

Written 26 September 2026. Covers work done 26 September 2026.
Committed at `5f27bc7`, `e90409f` and `8198a4e`. 373 tests passing, 97% coverage on `src/qbench`.
**Revised three times**: after the fraud arms were audited with the hook, again
after the full per-family surrogate run on the fraud bandwidth arm established what the
audit had only indicated, and once more on 27 September after the churn equivalent came back
a weaker result than fraud's rather than a matching one. Section 13 listed
that as an open gap and it is now closed; sections 4, 9, 10, 11 and 13 are updated, and the
fraud bandwidth arm produced the strongest single result in this record.

**No deviation record was opened this week.** D6 was challenged twice, on two different
grounds, and every one of its nine figures reproduced exactly. Both challenges were mine
and both were wrong. That is recorded in sections 6 and 10 rather than buried, because a
record surviving an attack is evidence about the record and a wrong attack is evidence
about the attacker.

Week 5 produced no new experimental data. Every number here comes from records already on
disk at the end of week 4, read by tools that were wrong when the week began.

---

## 1. What week 5 was for

Week 4 ended with the project turned toward the audit protocol, and with four checks
listed in the protocol as Tier 2: not runnable from a results file, reported as NOT RUN
with the reason. The week's stated task was to build an interface so a pipeline that can
supply its kernels gets those four checks.

That framing was half wrong before any code was written. "Not runnable" is a claim like
any other, and the four had been written off in one sitting without the question being
asked separately for each. Asked separately, three of the four were runnable: one needed
nothing at all, two needed only an interface. The remaining one genuinely needs a re-run
rather than a hook.

The second half of the week was not planned. The first run of the finished tool against
real records found six defects in its own checks, and the corrections consumed more of
the week than the feature did.

---

## 2. The check that needed nothing

`bandwidth tuning` was filed as Tier 2 on the grounds that knowing whether a kernel has a
scale parameter requires the embedding. That is true and it is beside the point. A method
whose **selected** hyperparameters never vary across records had nothing to select from,
and one whose parameters vary had a grid. The contrast is in the records.

It is now the Tier 1 check `tuning symmetry`, and on this project's registered churn file
it reads:

> `linear` 1 structural / 9 C (no parameters); `poly` 99 structural / 9 C;
> `quantum-angle-r1` 1 structural / 6 C; `quantum-angle-r2` 1 structural / 8 C;
> `quantum-iqp-r1` 1 structural / 7 C; `quantum-iqp-r2` 1 structural / 7 C;
> `rbf` 10 structural / 7 C.

Four quantum settings recording parameters that never varied, against a classical arm
searching ten RBF bandwidths and ninety-nine polynomial settings. That is the defect that
cost this project four weeks, visible in one line, from records that existed in week 3.

It warns rather than fails, because a wide grid with one consistently winning value looks
identical from selections alone. The report says so instead of choosing.

On the bandwidth arm the same check passes, because the quantum settings then select
between three and five distinct bandwidths. The two readings together are the cleanest
statement of the bandwidth defect the project has produced.

---

## 3. The hook, and the one line that makes it trustworthy

`kernel conditioning` and `classical surrogate equivalence` ask about the kernel, and a
results file records what a model scored. They now run when the caller supplies `--hook`:
a module exposing up to three functions, with no base class, no registration, and no
import of `audit` itself.

```python
def gram(record)            # -> (n_train, n_train) training Gram matrix
def training_data(record)   # -> (X_train, y_train)
def refit(record, gamma)    # -> a record-shaped dict for a surrogate kernel
```

A check needing a function the module does not define reports NOT RUN and names it.
`scripts/audit_hook_qbench.py` is this project's adapter and the worked example.

The dangerous failure of a hook is not that it raises. It is that it rebuilds the split
**differently** from the pipeline that wrote the records, so the audit measures a kernel
the experiment never used and produces confident readings with nothing to distinguish
them from correct ones. The defence is four lines in `refit`: it compares the resulting
test-label fingerprint against the record's and raises on a mismatch, and the audit then
reports FAIL rather than a number. A test pins that behaviour. It is the only part of the
example hook that anyone writing their own must copy.

---

## 4. What the hook found

**Conditioning.** Condition numbers of 7.8e+19 on the registered churn arm and 9.9e+21 on
the bandwidth arm, across all four settings. Both are seven to nine orders past the 1e+12
threshold at which the SVM dual stops being determined, which is consistent with D2's
measured range and confirms that threshold-based tests such as McNemar were never usable
here. Rank statistics survive, and everything reported in this project is a rank statistic.

**Surrogate equivalence, and a correction to week 4's reading.** At the **registered**
bandwidth, every sampled kernel separates from its nearest label-free RBF surrogate:
median 0.0050 in normAP, range 1.35e-03 to 6.48e-02, all above D2's floor, covering all
four settings on six seeds. At **tuned** bandwidths, two of six sampled kernels fall below
the floor, median 3.04e-03, range 0.00e+00 to 2.89e-02, and the check reports it as too
close to call.

**Fraud, both arms, added on revision.** The registered fraud arm reads too close to call:
median 3.95e-03, one of six below the floor, range 6.54e-04 to 2.40e-02. That follows from
both arms sitting at 0.966 average precision with 0.034 of headroom — a kernel with that
little room to move has little room to separate from its surrogate.

The fraud **bandwidth** arm is the first arm in this project to return the outright verdict:

> over 6 sampled kernels the median difference from a label-free RBF surrogate is
> **1.66e-04** in normAP, below this pipeline's reproducibility floor of 1e-03, over 4
> methods on 6 seeds. On this evidence the kernel is its surrogate and the comparison is
> classical-versus-classical.

Six times below the floor, across all four settings. This is Flórez-Ablan, Roth and
Schnabel (2025) reproduced inside this project's own pipeline, measured in endpoint units
rather than kernel-space distance, with no labels used in fitting the surrogate. **The full per-family run, added on second revision, establishes it.** All four settings,
twenty seeds each, through `scripts/rbf_surrogate.py` with the three-condition rule:

| setting | median gamma | d normAP | 95% CI | p |
| --- | --- | --- | --- | --- |
| angle-r1 | 3.981e-03 | +0.0003 | −0.0008 to +0.0015 | 0.0353 |
| angle-r2 | 1.585e-02 | +0.0001 | −0.0009 to +0.0010 | 0.0681 |
| iqp-r1 | 5.623e-03 | −0.0006 | −0.0023 to +0.0011 | 0.0973 |
| iqp-r2 | 6.310e-03 | −0.0010 | −0.0027 to +0.0008 | 0.0897 |

Every interval spans zero. Both families come in below D2's floor: angle at +0.0002 and IQP
at −0.0008, neither a measurement. The rank tests do reject — angle at p = 0.0055 — and the
three-condition rule refuses to call that an effect, which is the machinery built after week
4's "finding declared on noise" working as intended.

**80 of 80 fitted gammas fall inside 1e-03 to 1e+02, the classical RBF grid the baseline
searched in week 2.** These are not exotic kernels found post hoc to match. The classical
arm had already fitted kernels functionally indistinguishable from every tuned quantum
kernel on this dataset, before the quantum arm existed.

**Churn does not reproduce this, and the difference is the point.** Run under the same code,
churn's tuned arm gives angle −0.0033 [−0.0076, +0.0010] and IQP +0.0045 [−0.0036, +0.0126].
Neither clears the three-condition rule, so neither is a detected effect — but both point
estimates sit three to four times *above* the precision floor, and what fails is the
interval excluding zero, not the magnitude. That is an underpowered null. Fraud's is a
sub-floor identity. Reporting both as "the kernel is its surrogate" would state the weaker
result at the strength of the stronger one, which is the error D6 exists to prevent one
level up. Churn's 80 of 80 gammas also fall inside the searched grid.

The audit's six-sample median was 1.66e-04 against family effects of +0.0002 and −0.0008
from eighty records. The stratified sample agreed with the full run in direction and
magnitude, which is the first evidence that the section 5 sampling fix produces readings
worth acting on.

Conditioning on fraud reaches 1.1e+33 registered and 7.5e+26 tuned, worse than churn by
thirteen orders and further evidence that nothing threshold-based was ever usable here.

So the collapse into classicality is a property of the **tuned arm**, not of the angle
family. An earlier reading in this session held that angle kernels sit at their classical
limit generally and IQP kernels do not; that was drawn from a sample which, it later
turned out, contained nothing but `angle-r1` (section 5, defect six). At the registered
bandwidth all four settings do something their nearest classical kernel cannot. What they
do is lose to the best classical kernel anyway, which remains the finding.

---

## 5. Six defects in the audit's own checks

Every one was in a check. None was in the records. The full test suite passed on all six,
and five were found by reading a report on real data rather than by any test.

1. **Negative control measured spread over records, not splits.** A control file holds
   several methods and settings scored on each seed's split; those records share the split
   and are not independent draws. Dividing by the square root of the record count when the
   unit is the seed doubled every sigma on a four-setting control, turning +1.40 into
   +2.68 and producing a FAIL on the bandwidth arm. The fifth instance of the
   unit-of-analysis error in this project and the second inside the tool written to catch
   it.

2. **Cross-arm silently discarded two thirds of a comparison file.** Handed a
   one-configuration quantum file and a fifteen-configuration classical file, the field
   inference intersected to nothing, every configuration collapsed onto one key, and the
   check kept whichever record it read last: **40 of 60 records dropped**, a clean PASS,
   and a plausible minimum detectable effect computed from the survivors. This is D6's
   error — power measured on the wrong pairs — committed by the check written to catch
   D6's error. The label fingerprint did not save it, because configurations differ in the
   feature mapping and not in the labels. It now refuses to pair when a
   (seed, configuration, method) key holds more than one record.

3. **Tuning symmetry fired on every linear baseline.** A linear kernel has no structural
   parameter, so it cannot be untuned, and counting it as untuned made the check warn on
   almost every comparison. A check that fires on everything carries no information. It
   now distinguishes an empty parameter set from a fixed one and names the parameters that
   were held fixed.

4. **The surrogate check called a sample straddling the precision floor a separation.**
   PASS at a median of 0.0012 against a floor of 0.0010, on six samples, with no spread
   reported, while the full per-family analysis of the same arm concludes the kernel *is*
   its surrogate. The measurement agreed with that analysis; only the verdict rule
   disagreed. A PASS now requires every sampled kernel above the floor, not the median,
   and the range is always printed.

5. **Unit of analysis skipped single-configuration files.** It reported that independent
   units could not be identified, which is false — the split is the unit — and it skipped
   exactly where an 80-record file most invites being read as 80 observations. One of this
   project's own tests asserted that SKIP, so the defect was being held in place by a
   passing test.

6. **The hook sample was one kernel family, twice.** `recs[::len(recs)//k]` aliases with
   the order records are written in. This project writes configuration-major, then seed,
   then setting, in blocks of 80; a stride of 200 against a period of 80 lands on setting
   index 0 every time. The first real run returned six records that were all
   `quantum-angle-r1` on two seeds. Every hook-based number in that report — conditioning
   at 2.0e+81 included, which is an `angle-r1` artefact — described one family while the
   text called it a sample of the file. Sampling is now stratified by method and staggered
   across configurations and seeds, and both checks print the methods and seeds they
   covered, because a sample that cannot be seen is a sample that quietly becomes one
   family again.

The pattern across all six: four were wrong verdict rules applied to correct measurements,
and two were wrong measurements. In no case did the number disagree with the underlying
data; in four cases the rule disagreed with the number.

---

## 6. D6, challenged twice and unmoved

D6's power table is the most citable thing in this repository. It was assembled by reading
numbers out of audit output and typing them into markdown, by a tool that turned out to
have six defects, and this project has already destroyed results by hand-transcription.
`scripts/audit_sweep.py` now regenerates it from the records and prints each row beside
what D6 claims.

**First challenge.** The bandwidth row appeared not to reproduce: D6 claims
0.0353 → 0.0233, the sweep measured 0.0307 → 0.0203. That was the sweep comparing D6's
figure against the wrong column. D6 quotes the variance of the pair H1 forms; the sweep
was computing a median over every method pair in the cell. Different question, different
number, and D6 was answering the right one.

**Second challenge.** D6's primary-cell row for churn is 0.0921 → 0.0608, and 0.0921 is
also the arm-level median to four decimal places. That identity was read as an arm-level
figure mislabelled as a primary-cell one. It is not. It is the coincidence D6's own
correction note records in writing — a note which had been read and quoted from in the
same session. The inference was drawn from a pattern the record explicitly warns about.

With the right quantity computed, all nine figures reproduce:

| row | quantity | D6 says | measured |
| --- | --- | --- | --- |
| churn 250 registered | arm | 0.0608 | 0.0609 |
| churn 100 registered | arm | 0.1005 | 0.1005 |
| churn 50 registered | arm | 0.1368 | 0.1368 |
| fraud 250 registered | arm | 0.0138 | 0.0138 |
| fraud 100 registered | arm | 0.0365 | 0.0365 |
| fraud 50 registered | arm | 0.0571 | 0.0571 |
| churn 250 registered | H1 pair | 0.0608 | 0.0608 |
| fraud 250 registered | H1 pair | 0.0063 | 0.0063 |
| churn 250 bandwidth | H1 pair | 0.0233 | 0.0233 |

D6 needs no correction. What the sweep adds is that the table is now regenerated rather
than transcribed, and that each of its two tables is labelled with which quantity it holds.

---

## 7. Three quantities, and which one a bound quotes

The sweep separates three numbers this project has conflated twice:

* **arm level** — the median over every configuration and method pair in the file. What a
  claim about "the churn 250 arm" rests on.
* **primary cell** — the median over every method pair inside the pre-registered cell.
* **H1 pair** — the paired variance of best quantum against best classical, each selected
  per seed by the registered inner-score rule.

An exclusion bound on the primary test is a statement about the pair the test forms, so it
must be measured on that pair. Quoting a median over all method pairs instead substitutes
the variance of comparisons nobody made, which is D6's own error one level down. They
differ materially: on churn at 100 per class the three are 0.1005, 0.0667 and 0.0423.

---

## 8. One of eight arms

| arm | observed | its own MDE | resolvable |
| --- | --- | --- | --- |
| churn 250 registered | −0.0798 | 0.0608 | **yes, 1.31x** |
| churn 100 registered | −0.0287 | 0.0423 | no |
| churn 50 registered | −0.0331 | 0.1027 | no |
| churn 250 bandwidth | −0.0101 | 0.0233 | no |
| fraud 250 registered | −0.0028 | 0.0063 | no |
| fraud 100 registered | −0.0088 | 0.0210 | no |
| fraud 50 registered | −0.0130 | 0.0432 | no |
| fraud 250 bandwidth | +0.0002 | 0.0032 | no, and below D2's floor |

One of eight arms produced a difference its own comparison could resolve. Every other
observed value in this study is smaller than the resolution of the comparison that
produced it. That is neither evidence of equivalence nor a measurement of a small effect,
and the distinction is the whole reason the power column exists.

Every sign favours the classical kernel except fraud's bandwidth arm at +0.0002, which is
three times below the reproducibility floor and is not a measurement either.

This changed one sentence in the README. The bandwidth collapse to −0.0101 was reported
without saying that the corrected arm resolves 0.0233, which invites reading the collapse
as a measured near-zero. It now says both.

---

## 9. Predictions made and scored

Twenty-seven explicit calls were written down before the runs that tested them, tagged
Certain, Likely or Guessing. Twenty-one held. Six failed:

1. The bandwidth arm's `tuning symmetry` would PASS. It warned — because of defect three.
2. The bandwidth arm's surrogate check would WARN. It passed — because of defect four.
3. The registered arm's surrogate range would **widen** once IQP entered the sample and
   the verdict would stay WARN. Both halves wrong: the range's floor rose from 0.00e+00 to
   1.35e-03 and the verdict became PASS.
4. D6's churn primary-cell row was the arm-level figure mislabelled. It was not.
5. The H1-pair column would differ from both other columns on every row. On churn 250 it
   equals the arm-level figure, which is the documented coincidence.
6. At least one churn family would clear the floor in the tuned arm. Neither did. The
   reasoning conflated "exceeds the precision floor" with "clears the three-condition
   rule": both point estimates *do* exceed the floor, and what fails is the interval
   excluding zero. Predicting on one of three conditions, in a project whose own rule
   requires all three, having built that rule.

Two further calls were right in verdict and wrong in magnitude: the bandwidth arm's
negative-control sigma was predicted to halve to 1.34 on the reasoning that four settings
within a seed are perfectly correlated. They are not, and it is 1.65.

The four calls made about the fraud arms on revision all held, including the [Guessing]
one: that fraud's bandwidth arm would land either at "too close to call" or at a genuine
below-floor reading, and that the second would be the stronger claim. It was the second.

Failures one and two were useful: each exposed a defect. Failure three corrected a
substantive claim about which arm the classicality collapse belongs to. Failures four and
five cost two turns and produced nothing.

---

## 10. Errors made and caught this week

Recorded because the count matters more than the average. The six code defects are
section 5; these are the rest.

1. **A verification claimed but not performed.** The README's AI-use declaration was
   reported as written and verified on disk at a stated line number. It was not on disk at
   all; the transfer had failed silently and the verification described was never run. The
   same error as week 4's cross-arm "on matching test points" claim, and the second
   instance. Every file transfer this week was subsequently staged back and diffed before
   being reported as landed.
2. **An inference drawn from a coincidence the record warns about.** Section 6. D6's
   correction note documents that two of its figures coincide to four decimal places and
   that the coincidence once survived review; that note was read and quoted from, and the
   inference it warns against was made anyway, twice, and stated as [Likely].
3. **Four checks written off in one sitting.** Section 1. Three of the four were runnable.
   "Not runnable" was asserted rather than measured, which is the failure the tool exists
   to catch, committed inside the tool for the second time.
4. **A test that held a defect in place.** `test_unit_of_analysis_skips_with_one_configuration`
   asserted the buggy behaviour. It was written to document a decision and became a lock
   on it.
5. **A number computed, printed and ignored** (found on revision). The `selection` check
   measured the rank correlation between inner score and test score, printed it, and
   passed regardless. On the fraud bandwidth arm it printed **−0.367** under the heading
   "Selection auditable". A non-positive correlation means the selection criterion carries
   no information about the quantity it selects for, which on that arm corroborates the
   surrogate verdict exactly: if every candidate is the same Gaussian kernel, inner-CV
   selection among them is ranking noise. The check now warns on a non-positive
   correlation. The boundary is the sign, not a chosen threshold. This is the same shape
   as defects three and four in section 5 — a measurement taken correctly and then not
   used — making it the third instance this week.

---

## 11. Tests and housekeeping

373 tests, up from 357, all passing; coverage on `src/qbench` unchanged at 97%.
`tests/test_audit.py` grew from 54 to 70 tests, fourteen of them regression tests for the
six defects, each verified to fail against the version that shipped. Two pre-existing
tests were rewritten because they asserted behaviour now known to be wrong.

`src/qbench` was not touched this week. Every change is in `scripts/` and `docs/`, so no
experimental result is affected by any of it.

---

## 12. Decisions taken this week

* **Three checks move out of Tier 2.** `tuning symmetry` to Tier 1; `kernel conditioning`
  and `classical surrogate equivalence` to hook-based. One remains genuinely unrunnable.
* **A hook check that cannot verify its split fails rather than reports.** Fingerprint
  mismatch is FAIL, not a warning, because the alternative is a confident number about a
  kernel the experiment never used.
* **Power figures are regenerated, never transcribed.** `scripts/audit_sweep.py` is the
  source for D6's table, and the JSON it emits is committed as provenance.
* **A surrogate PASS requires every sampled kernel above the floor**, not the median.
* **The sample's coverage is printed with every hook-based reading.**

---

## 13. Still open

* **Churn's tuned arm is an underpowered null, not a demonstration of equivalence** (added
  on third revision). Re-run under current code it gives angle −0.0033 [−0.0076, +0.0010]
  and IQP +0.0045 [−0.0036, +0.0126]: both point estimates three to four times the
  precision floor, both intervals spanning zero. It excludes an effect the size of the
  registered arm's +0.0852 and cannot exclude an effect the size of its own point estimate.
  Resolving it needs more seeds on that arm, not more analysis of these twenty.
* **`grid adequacy against a shuffled null`** remains the one check that needs a re-run
  rather than an interface: the same pipeline on permuted labels with a widened grid.
* **The pre-registration's section 1 rewrite**, for the turn toward the protocol. This is a
  larger deviation than anything in D1 to D6 and needs its own record. It has not been
  started.
* **OSF registration**, on hold pending that rewrite.
* **The filesystem backup from the history rewrite** can be deleted once GitHub has been
  confirmed in a browser.

---

## 14. Week 6

The protocol is now the deliverable and it has been exercised against real data exactly
once, on one dataset, finding six defects in itself. The second dataset was done on revision and found a seventh, in the
`selection` check.

That run was done on second revision and the finding held on fraud: at tuned bandwidths the
quantum kernels there are Gaussian kernels the classical baseline had already searched. The
churn equivalent, run on third revision, is an underpowered null rather than the same
result, and closing that gap needs seeds rather than analysis.

The next step is the section 1 rewrite, which is the last thing standing between this project
and a registration that describes what it is actually doing.

---

## 15. What this week says about the project

Week 4's lesson was that a literature search is not optional. Week 5's is narrower and
less comfortable: **a green test suite is not evidence that a measurement tool measures
anything.** Six defects, 357 passing tests, and five of the six found by a person reading
output on real records. The tests were not bad — they were written against the same
misunderstanding as the code, which is what a test written by whoever wrote the code
mostly checks.

The protocol's own section 6 now says this about itself, which is the only honest place
for it. A tool that audits method has no standing to exempt its own method, and this is
the second week running in which the audit's largest findings have been about the audit.
