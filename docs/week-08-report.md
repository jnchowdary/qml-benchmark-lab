# QML Benchmark Lab: Week 8 Record

Written 29 September 2026. Covers work done on 29 September 2026.

**Three deviation records opened: D12, D13, and a third amendment to D11.**
D12 and its amendment drop the hardware runs. D13 declares a departure that had
been in force and undeclared since 25 September. D11's amendment records that
this project's git history was rewritten, which destroyed the two commit hashes
the pre-registration cites as its anchor.

**The headline.** Week 8 was meant to be consolidation. It found three false
provenance statements in the pre-registration, a rewritten history whose only
surviving original copy was in a folder queued for deletion, and a confirmatory
test that had been reported in defiance of its own registration gate.

---

## 1. What week 8 was for, and what it turned into

Week 7 closed with all three registered confirmatory hypotheses tested and two of
them returning no verdict. The last clear execution week before the plan turns to
writing was offered as a choice between consolidation, an attempt at the hardware
runs, and starting the write-up early. Consolidation was chosen, with the IBM
allocation to be checked regardless.

The consolidation happened and is sections 2 to 6. Sections 7 to 10 are what the
consolidation uncovered, none of which was on the list.

---

## 2. The file that produced both confirmatory verdicts had no tests

`scripts/geometric_tests.py` executed H2 and H3 on 29 September and returned NOT
ESTABLISHED for both. At that moment it was 822 lines with **no tests at all**,
in a repository holding fifteen test files including 73 for `audit.py`. Twelve
defects had been fixed in it that day, each caught by a control, by an output
line that looked wrong, or by the code raising on first execution, and nothing
held any of the fixes in place.

`tests/test_geometric_tests.py` adds **30 tests**, one per defect plus the
aggregation rules from D7 and D8 and a negative control. `tests/test_stats.py`
adds **21**. The suite goes from 376 to 430.

---

## 3. The tests passed first time, which by this project's standard is a warning

28 of 28 passed on the first run. Nothing had shown that a single one of them
would fail against the code it claimed to pin, and a regression test that passes
against both the fixed and the broken version is decoration.

`scripts/mutation_check.py` reverts each fix one at a time, runs only the test
that names it, and requires the run to **fail**. Thirty mutants across two files,
every touched file restored and hash-verified afterwards. It found **four tests
that were decoration and a fifth that needed three attempts**:

**H3's MIN_UNITS guard.** The test built eight units with g = 1..8, which the
g = 2 split divides six above and two below, so `min(above, below) < 3` refused
on the degenerate partition and the guard the test claimed to pin was never
reached. Deleting that guard changed nothing.

**The precision floor.** Its differences were constant at 1e-9, so after the NaN
guard went in `h2` returned NOT ESTIMABLE before `n_above_floor` was computed,
and the assertion had been loosened to `r.get("n_above_floor", 0)` to make it
pass. That default made it true for any value of `FLOOR`. **The assistant
loosened that assertion earlier the same day**, which is how a test stops
testing.

**The controls.** Named "all nine", called only `test_controls()`, which is five.
Controls A, B, C and I live in `controls()` and were never invoked.

**The fast path.** Its kernels had a unit diagonal, where `normalise_kernel` is
the identity, so removing the normalisation entirely changed nothing it could
see.

**The CLI, three times.** `"--test" in help_text` stayed true when the flag was
renamed `--test-GONE`. A word boundary did not help either, because `--units`'s
help string reads "sweep output to test (with --test)", so the assertion was
satisfied by prose in another argument's help text. It now reads
`build_parser()._actions` directly, which required extracting the parser from
`main()`.

---

## 4. One defect in ten places, and an audit check that passed on nothing

Running the full suite surfaced `ConstantInputWarning` from `audit.py` and
`rbf_surrogate.py`. `scipy.stats.spearmanr` returns NaN on a constant input, and
every comparison against NaN is False:

    nan <= 0     -> False    a "warn if not positive" branch never fires
    nan < 0.05   -> False    a "rejects" flag reads as no rejection
    nan * r > 0  -> False    an agreement check silently disagrees

Each turns an undefined correlation into a definite verdict, and always the
reassuring one. **Ten call sites existed. Two were guarded, both by the assistant
an hour earlier**, in the file it happened to have open -- the same partial fix
`rbf_surrogate` made when it guarded two of three inputs. Three had been printing
that warning on every `make test` run for weeks and nobody read them.

`src/qbench/stats.py` holds the refusal in one place. `rho` is `None` rather than
NaN on refusal, so a caller who ignores the `ok` flag gets a `TypeError` instead
of a wrong answer; that guardrail is the reason it is a type and not a tuple.

**The verdict change.** `audit.check_selection_leak` returned **PASS** when the
correlation was undefined, reporting "selection is auditable and the criterion
tracks the endpoint" about a number that does not exist. Its own comment four
lines above claimed this class of defect had been fixed once. It now SKIPs and
names the constant input, consistent with the audit's rule that a check unable to
answer its question says so rather than reading absence as a pass. **Nothing in
426 tests would have caught that change in either direction**: the constant path
had no coverage. `with_inner(0)` produces exactly that case and the helper
supported it from the start; no test had ever passed 0.

---

## 5. A standard error that printed as zero

`tekeli_check.py` rendered `slope_stderr` at `.3f`. Two of the four settings in
`results/audits/tekeli_churn_small.json` carry 3.168e-04 and 3.099e-04, and
**both printed as `0.000`** -- indistinguishable from 1e-07, and from a fit that
had resolved nothing. Open since week 6, where it was named and not fixed.

`fmt_pm` uses significant figures, so those now read 0.00032 and 0.00031. This is
the third member of a family: `0.00e+00` for an underflowed p-value, `9/8` for a
count printed without its denominator, and `0.000` for a standard error. Each
converts a small number into a false certainty at the display layer, after the
arithmetic was correct.

---

## 6. The hardware runs were never feasible, and the number was in every record

Section 13 registers "Weeks 7 to 8: IBM hardware runs on the primary cells". Week
7 ended with no hardware and no hardware code. The allocation, listed as
unconfirmed in weeks 1, 2 and 3 and never checked, is **10 minutes of QPU time
per month**, with the trial account expiring in one day and no workload ever
submitted.

**Corrected 25 October 2026, D18: `circuit_evaluations` is a circuit count and
not a hardware cost.** Hardware estimates each kernel entry from S shots, so the
executions a QPU meters are this count times S, and no shot count exists
anywhere in this project. Every figure in the paragraphs below is therefore a
floor rather than an estimate; the conclusion they support -- that the registered
run was never feasible within the allocation -- holds by a wider margin than they
give. They stand as written, as a weekly record.

Every quantum record already carries the hardware-equivalent cost, because D1
required it: `circuit_evaluations` = 113,575, being 61,075 training pairs plus
52,500 test pairs. The registered scope is 4 settings x 20 seeds x 2 datasets:

    18,172,000 circuit executions against 600 seconds per month

30x over budget at 1 ms per circuit, 150x at 5 ms, and still 3x over at an
implausible 0.1 ms. **Section 13 allocated two weeks to a run the available
hardware could never have delivered**, and the number proving it has been printed
in every quantum record since week 4, in a field created so hardware cost would
not be misreported.

Hardware appears in the timeline only; no hypothesis, endpoint or decision rule
mentions it, so nothing registered depends on it. One (setting, seed) Gram would
have fitted in the 600 seconds and would have given the audit protocol its own
hardware records rather than the borrowed ones it audited in week 6. Declined:
no hardware code exists, the trial lapses tomorrow, and writing a Qiskit Runtime
path to a deadline produces untested code -- the failure mode this week spent its
day repairing.

---

## 7. Two of three published claims about a second third party were wrong

Section 15 of the week-4 record asserted of Flórez-Ablan, Roth and Schnabel: "no
average precision, no chance-level correction, no negative controls." This was
the first application of the rule that record set for itself: *a claim about what
another group did not do must cite their code or their data, or it is not made.*

**"No average precision" stands.** They report ROC-AUC, verbatim in Section III C
and the Figure 5 caption.

**"No chance-level correction" is a category error.** ROC-AUC has a fixed chance
value of 0.5 regardless of base rate. Chance correction matters for average
precision *because* AP's chance level is the positive rate, which is why this
project built normAP. **Week 6 recorded the identical category error about
Kakavand et al. on 27 September**, and section 15 was never re-read against that
correction, so the same mistake sat four hundred lines away in the same document
for two days.

**"No negative controls" is withdrawn as unverified.** Their Section III states
the code is on GitHub; the claim is still untested against it and reference [54]
carries no resolvable URL. The check remains open.

**Running tally: nine claims published about two other groups' work, seven
failed on checking.**

---

## 8. Three false provenance statements, and a history that was rewritten

The pre-registration's header and closing line claimed **"Registered 24 September
2026"** and **"Registered at OSF. Any version of this document other than the
registered one is a draft."** There is no OSF registration, no identifier, no DOI,
and none was ever created. Those statements were live on a public repository from
24 to 29 September, across five weekly records, ten deviation records, the
publication of the audit protocol, and contact with three named researchers about
a protocol for auditing other people's methodology. Weeks 1, 2 and 3 each
recorded that an external timestamp was needed "before week 6, not after"; week 4
put it on hold correctly; week 5 held it pending a rewrite that D6 forbids and
week 6 records as never having been required.

**Software Heritage has never archived the repository** -- HTTP 404, origin
unknown -- so no third-party timestamp exists for anything here.

**The third claim was worse.** Line 5 read "Code state this design rests on:
commit `a8bafbb`. This document added at commit `61f7db9`. ... both are on `main`
and public." Neither hash exists in the repository. The history was rewritten on
25 September at around 22:22, changing every sha from the root onward. The cause
was mundane: the rewrite stripped `Co-Authored-By` trailers from every commit.
Root trees are byte-identical, no blob over 200 KB exists in the old history, no
credential path was ever committed, `data/raw` was never in version control. **A
cosmetic commit-message edit invalidated every hash in the project, including the
two the pre-registration depends on.**

**The assistant made it worse.** Commits from 26 to 29 September reinstate those
trailers by default, about thirty of them, so the repository ran two attribution
conventions either side of 25 September and nobody chose that. Resolved: prose
only, the README's AI-use section is the declaration, no trailers from here, and
the inconsistent stretch is documented rather than rewritten.

**How it was found.** Not by the audit protocol, the mutation harness or 430
tests. By a diff run on a 311 MB backup folder before deleting it, because
deleting it on an unverified assurance seemed like the same unchecked claim the
day had already produced twice. That folder held the only surviving copy of the
pre-rewrite history and was in `_to_delete` at the time. It is now preserved as
the local branch `prerewrite-20260925`, where both cited hashes resolve, and is
**not published**, because publishing would restore the trailers the rewrite
removed.

---

## 9. A confirmatory test was reported through a gate its registration keeps shut

Section 9 registers the confirmatory set as exactly three tests and says H3 "is
reported only if H2 is rejected". H2 was not rejected. H3 was reported in full
across five lambda columns, given its own section in the week-7 record, and its
lambda = 0.1 result called the strongest signal in the data at p = 7.93e-07.

The departure was decided in advance -- the week-4 record states it twice, before
any g existed, with a sound reason -- but section 11 requires departures to be
recorded in `deviations.md`, and none was. **D13 declares it four days late**,
and states two costs without softening: the confirmatory family is four tests
rather than three with no correction applied to it, and the "decided in advance"
defence rests entirely on commit ordering, which section 8 above has just
finished documenting as author-controlled, rewritten once and externally
unwitnessed. D13 gives both readings and lets the reader choose. H3 is not
re-gated, because imposing a reporting rule with the answer known is what D5
refused over lambda and D10 refused over breach tolerance.

---

## 10. Five shareable documents still carried the uncorrected text

Weeks 1 to 3 were transcribed into Word by hand and lived only at the top of
`~/Documents`, outside the repository. The pre-registration had no `.docx` in the
repository at all, so **the only Word version of the pre-registration in
existence was a hand-made file dated 24 September carrying all three false
provenance claims and the wrong author name**. It is the shareable copy.

All four are now generated by `report_to_docx.js` from the markdown, which is
what that script exists for. Before superseding the hand-made files they were
compared by extracted text rather than file size: week 4 had zero distinct words
present only in the old version, weeks 2 and 3 differed by 15 and 6 characters
with nothing over 20 characters unique, and week 1's two unique words were
transcription wording variants.

---

## 11. The pattern, which is one thing and not eleven

Every defect found today is the same failure in different materials: **something
that could be true for more than one reason was treated as evidence for one of
them.**

A test passing because a different guard fired. An audit check returning PASS
because `nan <= 0` is False. A flag appearing in help text because another flag's
help string mentions it. `"Registered at OSF"` appearing in a document because
the correction quotes it as false. `--test` matching inside `--test-GONE`. A
backup assumed redundant because its filenames matched.

The mutation harness is valuable precisely because it is the only instrument here
that distinguishes "this passed" from "this passed for the reason claimed". The
audit protocol, the controls and the 430 tests all check that an answer is right;
none of them checks that it is right for the stated reason, and none of them
looks at the repository's own history, which is where the three false provenance
statements lived unexamined for four days.

---

## 12. Four wrong claims of the assistant's, again

**Three mechanisms for the ceiling breach**, each refuted by the next
measurement, the third put forward as a finding and one message from the
permanent record before a stratified 60-cell sample refuted it. Recorded in D10
section 4.

**A surname.** A discrepancy between commits and documents was noticed, one side
assumed authoritative without asking, and the assumption published as a finding
in week 7 section 8 -- in a section about claims asserted rather than checked.
Neither spelling was the author's full name, including the one adopted as the
fix.

**A loosened assertion.** `r.get("n_above_floor", 0)` was written to make a
failing test pass after a behaviour change, which made it vacuous for any value
of `FLOOR`. Caught by the harness the same day.

**Reinstated trailers.** Thirty commits restored attribution metadata a history
rewrite had deliberately removed, unnoticed by either party for four days.

---

## 13. Still open

**The Flórez-Ablan code check.** Their code exists on GitHub per their Section
III; the "no negative controls" claim is withdrawn until it is read.

**`prerewrite-20260925` is local only.** The pre-registration cites hashes that
exist on one machine, in a branch recovered from a folder that had been queued
for deletion.

**No external timestamp exists** for anything in this project. Archiving at
intervals from now would make weeks 9 to 12 witnessed, which is what weeks 1, 2
and 3 each asked for.

**The confirmatory family is four tests, uncorrected**, per D13.

**Churn tuned-arm seeds**, 4x to resolve 0.003 to 0.005 against an MDE of 0.008.
**Grid adequacy check.** **`_to_delete`** holds the `Claude outputs` duplicates
and five superseded Word files.

---

## 14. What this week says about the project

The consolidation worked. 51 tests were added, every one of them shown to fail
against the defect it names, a cross-cutting NaN defect was closed at ten sites
with an audit verdict corrected, and two display defects joined the one from week
6 as a named family.

What matters more is what the consolidation found by accident. This project has
an audit protocol, a mutation harness, 430 tests and fourteen deviation records,
and none of them noticed that its central document asserted three things that
were false, that its history had been rewritten, or that a confirmatory test was
being reported through a closed gate. All three were found in the same two hours,
two of them by declining to accept an assurance that a folder was safe to delete.

The instruments this project built are good at checking whether an answer is
right. They do not check whether a claim about the project itself is true, and
that is where every serious problem found today was living.
