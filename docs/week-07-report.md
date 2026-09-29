# QML Benchmark Lab: Week 7 Record

Written 29 September 2026. Covers work done on 29 September 2026.

**Three deviation records opened: D8, D9, D10.** D8 and D9 were written before
any g existed on disk. D10 is marked POST-HOC in its own heading and changes no
verdict.

**The headline.** H2 and H3 were executed for the first time, five weeks late,
across all 360 registered units. The registered decision procedure returns **no
verdict for either hypothesis**. Section 2 of the pre-registration calls H2 "the
reason this project exists."

---

## 1. What week 7 was for

Week 6 closed with an open item that had been true since week 4 and had never
appeared in a weekly record: two of the project's three registered confirmatory
hypotheses had never been run. H1 was tested in week 4. H2 and H3 were not, and
the project turned toward the audit protocol and did not come back.

Week 7 ran them. It also produced three deviation records, thirteen defects in
this project's own code, and four wrong claims of mine that had to be withdrawn
in the same session in which they were made.

---

## 2. The verdict: NOT ESTABLISHED, for both hypotheses, at every lambda

D5 requires the registered conclusion to hold at every lambda at which no unit
breaches its sqrt(n) ceiling. **No lambda column is breach-free.** The procedure
therefore returns no verdict in either direction.

| lambda | units | breaches | rho | p | 95% CI | H2 | H3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1e-1 | 360 | 4/7200 | +0.1712 | 1.11e-03 | [+0.069, +0.270] | rejects | rejects |
| 1e-2 | 350 | 657/7200 | -0.0245 | 6.48e-01 | [-0.129, +0.081] | no | NOT ESTIMABLE |
| 1e-3 | 90 | 4574/7200 | -0.3814 | 2.09e-04 | [-0.545, -0.189] | rejects | no |
| 1e-4 | 61 | 4972/7200 | -0.2938 | 2.16e-02 | [-0.508, -0.045] | rejects | no |
| from C | 289 | 2893/7200 | -0.0145 | 8.06e-01 | [-0.130, +0.101] | no | on \|d\| only |

**Four breaches, one seed.** At lambda = 0.1 all four breaching observations in
7,200 are the same cell and seed: churn, n=100, selectk, 4 qubits, seed 7, poly
at C = 1e-04, once per quantum setting. That single seed voids the only lambda
column in which all 360 registered units survive, on 0.056% of the observations.

**The sign flips.** +0.1712 at lambda = 0.1, -0.3814 at 1e-3. Both reject. D5
pre-declared what to do when lambdas disagree: report that g's relationship to
observed performance depends on the regularisation chosen, which is a result
about the metric rather than a failure of the test.

**The two negative figures are weaker than they look.** lambda = 1e-3 excludes
270 of 360 units and 1e-4 excludes 299, both for exceeding the ceiling, so the
predictor's range is truncated from above. The only complete, unselected
population is lambda = 0.1, where rho^2 is about **0.03**: g accounts for roughly
three percent of the rank variance in observed difference. As a pre-training
screen that is close to worthless even taken at face value.

---

## 3. H3 points away from the hypothesis under test

At lambda = 0.1, median |observed difference| is **0.0235 above** the g = 2 split
and **0.0777 below** it. Gap -0.0542, CI [-0.1056, -0.0191], rank-biserial
-0.387, p = 7.93e-07, with D8(c)'s signed secondary also rejecting at p =
2.17e-06. **High geometric difference goes with smaller differences in
performance.** The prediction being tested is that a large geometric difference
is what permits a large quantum advantage.

Week 4 section 9 observed on eight seeds that g was highest where the quantum
kernel did worst, and could not say why. The full sweep reproduces the direction
at unit level across 360 units.

At lambda-from-C, the rule section 6 actually registered, rho = -0.0145 at p =
0.81, with 2,893 of 7,200 observations breaching and D8(b)'s above-floor subset
flipping sign to +0.0024. **The registered lambda rule yields no relationship in
either direction.** That is the case D5 made in advance, now measured.

---

## 4. All of it sits under D9

The observed difference every correlation above is measured against comes from
the registered arm, where the quantum kernels carry no bandwidth key at all --
their `params` are `{"embedding": "angle", "reps": 1}` and the default of 1.0
applies -- while the classical arm tunes its kernel by inner CV over a full grid.
Week 6 established that this asymmetry is the largest single effect in the
comparison.

**H2 as registered therefore tests whether g predicts a quantity this project has
already shown to be confounded.** The bandwidth-matched arm cannot substitute: it
covers one cell per dataset, churn at pca/12 qubits and fraud at selectk/8
qubits, 80 records each, giving 4 units per dataset and 8 in total against an
estimability floor of 12 and a registered universe of 360. H2 is NOT ESTIMABLE
there at every lambda, and the 8 units print descriptively.

---

## 5. What was built, and what it cost

`scripts/geometric_tests.py`, 822 lines. The sweep computes g per seed against
that seed's own inner-CV-selected classical kernel at D5's four frozen lambdas
plus lambda-from-C, hoisting `sqrt(K_C)` and the per-lambda solve out of the
setting loop for a fourfold saving. The test stage implements H2's Spearman,
H3's Mann-Whitney, D7's median-over-seeds aggregation with IQR, D5's per-lambda
ceiling rule with breach counts, and the per-seed sensitivity.

**Nine controls run before anything else and the script refuses to report if one
fails.** A, the fast path against the module, exact. B, g(K,K) against the
analytic mu/(mu+lam), 1.33e-15. C, an angle kernel at b = 0.02 against its fitted
RBF, 0.9975. I, the record's own params against bandwidth 1.0, bit-identical. D,
a monotone table giving rho = +1 and a SUPPORTED verdict. E, the median resisting
one wild seed where the mean does not. F, nine survivors leaving the table and
being counted. G, 3-versus-3 complete separation reproducing U = 9 and p = 0.1
exactly. H, no signal returning NOT SUPPORTED on both tests.

**The sweep.** 1,800 (cell, seed) combinations, 7,200 rows, 900 per dataset, 55.6
minutes: churn at 1.5 s/cell and fraud at 2.2. 360 distinct units against a
registered universe of 360, 20 seeds in every unit, nothing non-finite.

**The commit order is the point.** The analysis went in at `fd2eae0` and
`db30825` before the data existed. The data went in at its own commit before
either result was read. That sequence is what makes H2 and H3 confirmatory rather
than exploratory, and it is visible in the history rather than asserted here.

---

## 6. Thirteen defects, twelve of them in code written this week

**Shipped through three commits without being executed once.** `sweep()` raised
`AttributeError` on its first line of its first real run: `primary_tests.load`
takes a `Path` and `audit.load` takes a `str`, and this file used the wrong
module's convention. Three commit messages described the analysis as fixed in
advance of its data while the code producing the data had never run.

**The nine controls all test arithmetic and not one opens a file**, which is why
that survived. `check_inputs()` now resolves and loads every input before any g
is computed, and is labelled an input check rather than a control because it has
no known answer.

**A p-value underflowing to zero was printed as `0.00e+00`**, which reads as a
certainty no finite sample supplies. Same defect class as `tekeli_check.py`
printing `+/- 0.000`.

**A perfect rank correlation gave `arctanh(1) = inf`**, no confidence interval,
and therefore `ci_excludes_zero = False` -- so the verdict rule would have
reported the strongest possible result as NOT SUPPORTED. rho is now clamped at
1 - 1/(2n) and control D covers it.

**The sweep hardcoded `bandwidth: 1.0`** for every quantum Gram. Correct for the
registered arm by coincidence, since its params carry no bandwidth, and flatly
wrong for the bandwidth arm where selection varies by seed from 0.0625 to 1.0.
Grams now come from the record's own `params`.

**The arm was not in the resume key**, so a resumed run against the other arm
would have found the (dataset, size, cell, seed) key present and skipped
silently, leaving a file that looked complete and held two arms' g under one
label.

**Timing printed on the normal exit path but not the `--limit` one**, so the
smoke test produced no timing -- the only number it exists for.

**`--limit` alone samples the cheapest cells in the sweep.** The loop runs
mapping-major, so `--limit 3` measured pca at 4 qubits and the first 12-qubit
cell is 80 iterations away. `--qubits` and `--mappings` now allow the expensive
end to be timed directly: 7.7 s/cell at 12 qubits and 350 training points.

**H3 returned a verdict on 8 units where H2 correctly refused**, and the "of 360"
denominator read a complete 8-unit arm as a 98% shortfall.

**`--test` and `--units` were in the module docstring's usage block but never in
`argparse`.**

**A bare breach count with no denominator**, in the new code and in
`classical_limit.py`, which is section 7.

**And the reason all twelve were caught by controls or by reading output rather
than by a test: `scripts/geometric_tests.py` has no tests.** The repository holds
fifteen test files, including 73 tests for `audit.py`, and `test_classical_limit`,
`test_primary_tests`, `test_geometric_difference` and `test_rbf_surrogate` for the
other analysis scripts. Not one of them references `geometric_tests.py`,
`g_for_settings`, `units_at` or the sweep. **The 822 lines that produced both
confirmatory verdicts in section 2 have zero regression tests.**

Every defect above was found by a control with a known answer, by an output line
that looked wrong, or by the code raising on its first real execution. That is the
same pattern weeks 5 and 6 recorded, but here it has a simpler explanation than
"tests check the author's own misunderstanding": in this file there was nothing to
check it at all. The nine controls are not a substitute. A control proves the
arithmetic is right today; a regression test proves a defect that was fixed stays
fixed. Twelve fixes went in this week with nothing holding them in place.

---

## 7. A published table was wrong in every row, and "9/8" is why

Reading `deviations.md` back four days after publishing it, D5's lambda table
gives fraud **9/8** ceiling breaches at lambda = 1e-4. Eight seeds cannot produce
nine breaches.

`classical_limit.py` line 279 read `br = sum(1 for v in gr + gs if v > ceil)`,
pooling the registered-bandwidth g values with the selected-bandwidth ones into a
single count, and printed it bare. The real denominator is **16**. Every sweep row
overstated the breach rate by two: 1e-3 is 6/16 and 8/16, 1e-4 is 7/16 and 9/16.
The from-C row uses a different convention again -- registered bandwidth only,
out of 8 -- and drops 1/8 selected-bandwidth breaches on each dataset.

D5's argument is unaffected. Its **severity** is withdrawn: half the evidence
breaching is not most of it. Pooling two kernels' g into one count is the
unit-of-analysis conflation D6 records, one level down, and the sixth instance.

Both `classical_limit.py` and `geometric_tests.py` now print every count with its
denominator. **A count printed without what it is a count of is treated in this
project as a defect, not a formatting choice.**

---

## 8. Four wrong claims of my own, three of them about the same question

Week 6's record had a section called "Four wrong readings of my own." This week
produced four more, and three were successive attempts at one question.

**A recount that contradicted the script, where the script was right.** Checking
the breach counts, I compared every row against a ceiling of 18.71. The ceiling
is sqrt(n_train) and varies by arm: 18.71 at n=250, 11.83 at n=100, 8.37 at n=50.
Seed 7's g of 12.7 is under the first and over the second.

Then three explanations of what a ceiling breach measures, each refuted by the
next measurement:

1. **The classical kernel is near rank-deficient and that drives g.** Refuted by
   its own diagnostic: the lambda = 0.1 amplification is 2.491 in the breaching
   cell and 2.487 in a non-breaching cell at the same dataset, size, qubits and
   seed, both pinned at the 1/(4 lam) = 2.5 cap, and the breaching cell has the
   *lower* effective rank.
2. **`||K_Q||` is larger in the breaching cell.** It is not: 65.0 against 72.7
   while g is 12.72 against 2.96. Quantum effective rank did differ sharply, 1 to
   6 out of 140 against 54 to 137.
3. **Therefore D5 names the wrong side, and excluding on the ceiling selects on
   the arm under test.** Put to the founder as a finding and one message from
   being written into the permanent record. **Refuted** by a stratified 60-cell
   sample, 960 observations, sampled on design factors with g never consulted: at
   the lambdas where breaches occur in bulk the classical factor predicts a
   breach with AUC **0.815** and **0.825** while quantum concentration is
   *anti*-predictive at 0.394 and 0.346, and `var log a_max` rises from 0.16 to
   8.08 as lambda falls while `var log ||K_Q||` stays fixed at 1.67.

**D5's account is correct and the objection is withdrawn.** The warning text in
`geometric_difference.py` stands. What survives of the three attempts: the bound
holds in 960/960 and its looseness is the alignment term, rho(g/bound, alignment)
from +0.773 to +0.885.

**The falsifier I designed was too weak to corroborate anything**, and D10 says
so: at lambda = 1e-3 and 1e-4 the necessary condition holds for all 240 sampled
observations, so zero false negatives is guaranteed by the test rather than
earned.

**A different surname in every commit message, and then a wrong correction.**
Commits in this session and the last carried `Author: Nagesh Jonnalagadda` while
the pre-registration and README said `Nagesh Chowdary`. This paragraph originally
recorded that as an error introduced into the git history, and "corrected" the
commits to Chowdary from `5390514` onward.

**That correction was itself wrong.** The author's name is **Nagesh Kumar Jonnalagadda**, confirmed
on 29 September 2026. Chowdary appears in the GitHub handle and the earlier
documents; neither spelling used in any commit to date is the full correct name,
including the one this paragraph called the fix. The documents and all subsequent
commits now carry Nagesh Kumar Jonnalagadda; earlier commits stand as written, in both spellings,
because history is not rewritten here.

The lesson is not about a name. A discrepancy was spotted, one side was assumed
to be authoritative without asking, and the assumption was written up as a
finding — in a section whose entire subject is claims asserted rather than
checked. It is the same shape as the three refuted mechanisms in section 8 and
the two third-party corrections: confident resolution of an ambiguity that a
single question would have settled.

---

## 9. Two pre-declared warnings fired exactly as written

**D8's degenerate-partition clause.** At lambda = 1e-2, H3 put 349 units above
the g = 2 split and **1** below. It is reported NOT ESTIMABLE rather than as a
null result, because a fixed threshold that has stopped partitioning the data has
stopped being a test, which is different from p > 0.05.

**D7's aggregation check.** Per-seed rho at lambda = 1e-3 is -0.0233 at p = 0.23
against the unit-level -0.3814 at p = 2.09e-04. Part of that gap is a population
difference rather than aggregation, because the per-seed version retains
surviving seeds from units the unit-level version discarded whole. Both are
reported and the 360-unit version remains the confirmatory one.

Neither of these was a lucky catch. Both were written down before the sweep ran,
precisely so that the behaviour could not be discovered and then explained.

---

## 10. Process failures worth recording

**Deliverables were written to the repo for two days and never surfaced in the
conversation**, so the founder could not see any of the week's documents from
where he was working. Correcting that then went too far in the other direction:
`deviations.md` was delivered as a download three times in three consecutive
messages, each one stale the moment the next section was appended, leaving three
competing copies of a file that has exactly one home. All seven such files were
moved to `Documents/_to_delete/`; none contained anything the repo lacked.

**Two Word exports in the repo contradict their own sources.**
`docs/deviations.docx` predates D8, D9, D10 and the D5 correction.
`docs/week-04-report.docx` predates the section-9 correction appended to it. Both
are still outstanding at the time of writing.

---

## 11. Decisions taken this week

**D8, before any g existed.** The observed difference averages over exactly the
seeds that produced the median g. H2 is also computed above the precision floor
and the verdict requires that subset to agree, which can only weaken a result.
H3's signed version is pre-declared as a secondary rather than chosen afterwards.

**D9, before any g existed.** H2 runs on the confounded arm because that is what
section 6 registers, the confound is reported alongside the result rather than
used to justify substituting a different arm, and the bandwidth arm's 8 units are
descriptive only.

**D10, after the result.** D5's rule is recorded as ambiguous between two
readings and unsatisfiable under the strict one, and left there. **No
breach-tolerance threshold is introduced.** Choosing a tolerance with the result
on screen is the error D5 itself refused when it declined to pick the lambda that
made g behave. A future study wanting a breach-tolerant rule registers one before
its data exists.

---

## 12. Still open

**`tests/test_geometric_tests.py` does not exist**, and it is the first thing week
8 should produce. Twelve defects were fixed in `geometric_tests.py` this week with
no regression test behind any of them, in a file that produced two confirmatory
verdicts. Every defect in section 6 is a test case that can be written from the
failure that exposed it, which is how `tests/test_audit.py` reached 73.

**The confirmatory family is now complete and returns: H1 disadvantage on churn,
H1 not rejected on fraud, H2 no verdict, H3 no verdict.** That is the result to
write up, and it is not the paper the pre-registration anticipated.

**Extending the bandwidth arm to all 60 cells** would make H2 answerable on an
unconfounded comparison. Not attempted in week 7, no claim that it will be, and
the cost is why the arm was one cell to begin with.

**The Florez-Ablan code check.** Their claims are still flagged unverified in the
week-4 correction and they have public code.

**`+/- 0.000` in `tekeli_check.py`**, which hides whether a standard error is 1e-4
or 1e-7. Named in week 6, still not fixed, and the same defect class as section 7.

**Churn tuned-arm seeds**, 4x to resolve 0.003 to 0.005 against an MDE of 0.008.
**Grid adequacy check.** **`qml-benchmark-lab-BACKUP-20260925`**, 311 MB, on the
list since week 5.

**OSF registration** was never blocked and still has not happened.

---

## 13. What this week says about the project

The registered procedure was followed exactly and produced no answer. That is a
real outcome and it is reportable: a decision rule requiring zero ceiling
breaches across 7,200 observations is not satisfiable at this scale, and one seed
in 1,800 is enough to void a complete column. Recording that honestly is worth
more than a verdict obtained by relaxing the rule afterwards, and the temptation
to relax it was real, because lambda = 0.1 is the only complete population and it
rejects.

The more useful finding is the one that cost three wrong answers. g's relationship
to observed performance is not directionally stable under the regularisation
choice, it explains about three percent of the rank variance where it can be
measured cleanly, and at the split H3 registers it runs opposite to the
prediction. For a metric proposed as a pre-training screen for quantum advantage,
those three facts together matter more than any single p-value in section 2.

And the pattern from weeks 5 and 6 held again. Thirteen defects, twelve in code
written this week, none caught by a test and nearly all caught by a control with a
known answer or by reading output that looked wrong. The controls that mattered
most were the ones checking things I was confident about: that g(K,K) = 1, which
was false; that a perfect correlation would be reported as supported, which it
would not have been; that the classical side of g was inert, which it is not.
Three times this week I offered an explanation with a confidence the evidence did
not support, and each time the thing that caught it was a measurement I had
argued for taking rather than a test I had written.
