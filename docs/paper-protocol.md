# Section 5 — The protocol

**Draft, 4 October 2026.** Written under the framing recorded in D15, which
makes this section the paper's contribution rather than its methods appendix.

A comparison of quantum and classical kernels can be run carefully and still
mean nothing, because the ways it fails are not visible in its results. This
section specifies checks that are, says what each costs, and is explicit about
which of them is implemented tooling and which is a procedure performed by hand.

It audits **method, not results**. It never reports which model won. A failure
means a conclusion drawn from a file is not supported *by that file*; it does
not mean the conclusion is wrong.

---

## 5.1 Three parts, and only one of them is a tool

D15 describes this project's contribution as a process for checking equation
ordering, implementation fidelity, provenance, and the limits of the resulting
evidence. **The implemented protocol covers the fourth and part of the second.**
Saying so first is the point; a section that let the framing imply more tooling
than exists would be the error the protocol is for.

| part | what it checks | status | exercised on |
| --- | --- | --- | --- |
| **A. The record audit** | what a results file does and does not support | **implemented**: `scripts/audit.py`, `tests/test_audit.py`, a documented record format and a hook interface | this project's six arms; one foreign pipeline |
| **B. Source to implementation** | that a paper's printed equation, its stated interpretation, and its released code are the same thing | **procedure, not tooling**. No script. | two published papers |
| **C. Provenance** | that a result's stated origin can be resolved by a reader | **procedure, not tooling**. No script. | this project, against itself |

Parts B and C are written up here because they found things, and because a
reader deciding whether to repeat them deserves the cost. They are not claimed
as software.

---

## 5.2 Part A — the record audit

### The format

One JSON object per line; a record is one model, scored once, on one
train/test split. Nothing in it is specific to quantum kernels. Required:
`method`, `seed`, `n_train`, `n_test`, `test_base_rate`,
`test_average_precision`, `test_roc_auc`. Strongly recommended, with each
check degrading to SKIP and naming what its absence makes unanswerable:
`test_label_fingerprint` (the test labels hashed **in order**, without which no
paired test can be verified, only assumed), `shuffled`, `final_converged`,
`inner_score`.

The format is the load-bearing part. **A file that does not record enough to be
checked cannot be checked by anyone**, and the claim here is not that a
comparison lacking these checks is wrong — it is that nobody, including its
authors, can tell.

### What it asserts, and what it costs

Tier 1 runs from the records file alone: schema, chance correction, negative
control, pairing integrity, solver health, unit of analysis, statistical power,
precision floor, multiplicity, tuning symmetry, cross-arm comparison, selection.
**Cost: seconds, no access to the original pipeline.** This is the tier that
makes auditing a stranger's comparison cheap.

Tier 2 asks about the kernel, which a results file does not contain, so the
pipeline supplies three optional functions — `gram`, `training_data`, `refit` —
and the audit imports nothing of its own. It covers kernel conditioning and
classical surrogate equivalence. **Cost: kernel recomputation, which is the
dominant expense**; `--hook-sample` is the knob, and readings are indicative by
construction. They say *run the full analysis*, not *publish this*.

One check needs a re-run rather than a hook: **grid adequacy against a shuffled
null**, because widening a grid raises the best inner score even when nothing is
better, so hyperparameter edge flags never justify it on their own. **Cost: a
second full execution of the pipeline on permuted labels.** It is the most
expensive check here and the one most often skipped.

### What distinguishes these from diagnostics

Published work in this area is statistically careful. Kakavand et al. apply
paired Wilcoxon with an exact permutation fallback for small n, Friedman with
post-hoc Nemenyi, and both Benjamini-Hochberg and Bonferroni; their kernel
diagnostics compute condition number, effective rank, PSD-ness and the full
eigenspectrum; their preprocessing is leakage-safe and their two arms share one
hyperparameter grid — a symmetry this project's registered design did not have.
**That is more statistical care than this project had at the end of week 4**, and
the protocol does not claim otherwise.

What is added are **decision rules rather than diagnostics**: a measured
reproducibility floor below which a difference is reported as unresolvable
rather than small; classical surrogate equivalence expressed in endpoint units
rather than as a distance in kernel space; shuffled-label controls adjudicated
against both a sigma bar and that floor; cross-arm rather than within-arm power,
which differ by 2.3x to 3.9x in this project's own data. Computing a condition
number is ordinary. Refusing a verdict on the strength of one is not.

---

## 5.3 Part B — source to implementation

**No tooling exists for this.** It is a reading procedure, performed twice, and
it found something both times.

**The procedure.** Obtain the paper's source rather than a rendering — for
arXiv, the e-print LaTeX. Record the archive and file hashes. Locate the
equation as printed, with its subscripts. Locate the prose that assigns its
arguments. Locate the corresponding call in the released code. Then compare the
three, and label every resulting statement as what the source states, what the
implementation does, or what the comparison establishes.

**Why source rather than a rendering.** Earlier attempts in this project to read
Huang's Appendix F from PDF renderings returned transcriptions that were
internally contradictory on exactly the subscripts at issue, and a claim that
the appendix contradicted its own main text was drafted on that basis and
withdrawn when the LaTeX was read. **A claim about an equation's index placement
is worth no more than the characters it was read from.**

**Cost.** One download, the hashes, and an afternoon per paper. No compute. It
is the cheapest part of this protocol and it caught the largest thing.

**What it found** is in section 2: that Huang's F19 is the reversed ordered
comparison relative to Equation (5), that Flórez Ablan et al. read it the
natural way, and that the quantity they compare against √N is therefore
`g(K_Q‖K_C)` where the screening quantity is `g(K_C‖K_Q)`. It also found, in
their released code, ROC-AUC computed on hard predicted labels — making the
reported quantity balanced accuracy rather than a ranking measure — and `g_tra`
computed throughout and never compared to anything.

**What it does not establish.** Nothing about whether their conclusions are
wrong. An ambiguity inherited from an upstream appendix is a scope statement,
not an error attributed to the people who inherited it.

---

## 5.4 Part C — provenance

**No tooling exists for this either.** The procedure is: take the identifier a
result record stores for its own origin and try to resolve it as a stranger
would, from the public artefact alone.

**Cost.** Minutes, and it requires no access to anything the authors have not
already published — which is the point.

**What it found, run against this project.** Every one of the 15,120 result
records stores a `git_commit` that does not exist on the public repository. A
history rewrite invalidated all three stored hashes; they resolve only from a
branch recovered from a folder that had been queued for deletion. A
tree-identity mapping to public counterparts exists, and it reduces what must be
taken on the author's word without removing it: a reader can verify that the
counterpart carries the stated tree and cannot verify that the stored hash ever
did.

The project's own reproducibility section commits that every record stores its
commit. **That commitment was satisfied in form and unverifiable in practice for
nine days before anyone checked**, and it was checked only because a previous
amendment had documented the same trap for different hashes.

**The loss, bounded precisely.** What a reader cannot do is **independently bind
a historical result record to the code that generated it**. That is the whole of
it, and it is not nothing: they cannot confirm that the analysis code at run
time is the code now published, nor diff the two to see what differs.

**What remains independently checkable**: every analysis script, in full; the
data provenance, which is separate and unaffected, with sources and checksums in
`data/README.md`; the records themselves, which are intact; and the public half
of the tree-identity mapping — that each named counterpart on `main` carries the
stated tree.

**What a re-run does not do.** Executing the current pipeline on the current
data produces **new evidence about the current code**. It does not authenticate
the old records, because agreement would be consistent with the code having
changed in ways that do not alter these particular outputs, and disagreement
would not distinguish a code change from a data or environment change. A
reproduction and an authentication are different operations, and only the first
is available here.

---

## 5.5 What this protocol does not do

It does not tell you whether a quantum kernel is better. The hook widens what it
can see and does not change that: a surrogate reading is about the kernel, never
about which model won. It does not detect a wrong kernel implementation, a
mis-specified feature map, or a dataset leaking labels through preprocessing. It
cannot see analysis performed outside the file it is given. **A clean report
means the file supports the kind of claim being made, not that the claim is
true.**

Parts B and C are not automatable as written. Part B requires judgement about
what an equation means; part C requires knowing what a given repository's
history has been through.

---

## 5.6 The evidence for this protocol is weaker than its instance count suggests

This is the section a reader should weigh most heavily, and it argues against
the contribution.

**Every Tier 1 and Tier 2 check was written after the defect it catches.** The
protocol's own first section says so: each exists because a specific reading
went wrong here, usually after passing review. Seventeen deviation records and a
list of caught mistakes are **not** evidence that a tool catches a stranger's
mistakes. They are evidence that this project eventually noticed its own.

**The prospective evidence is one case, and what it shows needs stating
precisely.** In week 6 the audit was run against Kakavand et al.'s public
Zenodo deposit through an adapter. It produced **one measurement and eight
refusals**: kernel conditioning across all six deposited `ibm_fez` Grams, worst
4.5e+05, against this project's own 7.8e+19 to 1.1e+33; and eight statements of
what the deposit cannot answer — four required fields absent, so chance
correction, power and the precision floor each name their gap; no classical arm
in the hardware phase, so cross-arm has nothing to pair; one seed, so
unit-of-analysis warns and power cannot speak; no `inner_score`, so selection
cannot be shown.

**It found no defect in their pipeline, and was not looking for one.** The
week-6 record states it directly: *"None of this is a criticism of their work:
it is a map of what a reader can and cannot verify from that deposit."*

**The criterion by which this counts as useful, stated rather than assumed.**
The output is useful if it changes what a reader knows about the deposit's
evidential reach. Before the run, a reader could not say which questions those
records could answer; after it, they could, in seconds, without the originating
pipeline. That criterion is met. **It is a claim about a reader's state of
knowledge, not about the quality of the audited work**, and it does not
generalise to defect detection, because on the only occasion these checks met
foreign records they detected none.

Parts B and C add two cases apiece, but both were performed by the same party
that wrote the procedures.

**Seven things have gone wrong in public, and they are two different kinds.**
Collapsing them under one word was itself imprecise.

*Defects in the instrument (three).* On its first contact with real records the
tool required a field this project's own pipeline never emitted, collapsed
fifteen configurations into one, and **silently changed three answers**. The
first audit run against real records then found four further defects, **all four
in the checks rather than in the records**, with the full test suite passing on
every one.

The third is the registered adjudicator of grid adequacy. Section 7 of the
pre-registration names `scripts/check_grid_edges.py` as what decides whether a
grid is too narrow, and requires the decision to be made against a
shuffled-label null. The script computed that null when asked, printed it, and
told the reader to do the subtraction by hand, while on a real run printing a
verdict derived from the ratio of the gain to the minimum detectable effect.
Week 3 had already recorded that ratio as a defect, because the maximum over a
grid grows with the number of points searched and so cannot separate an optimum
lying outside the grid from a surface too noisy to rank; the threshold week 3
describes as pre-declared existed nowhere in the code. The committed log
`results/analysis/grid_edges_fraud.log` therefore carried the verdict
**UNDER-TUNED, widen the grids and re-run week 3**, where the registered
comparison returns adequate. The correct answer was in the week-3 record
throughout and the project acted on it, so no result here rests on the wrong
verdict; what was published was an instrument contradicting its own record for
three weeks. Found on 18 October 2026 by reading the script, not by any check in
this protocol.

*Claims its authors made that their own data does not support (four).* It asserted from the
manuscripts that two published benchmarks performed none of five checks; when
the deposit behind one was read, **six of seven claims in that paragraph were
wrong or misleading**. It declared four checks unrunnable when three were not —
one needed nothing at all. And the confirmatory script printed a **superseded
exclusion bound for eleven days**: `scripts/primary_tests.py` quoted the
registered 0.0059 for fraud's primary cell while every document here quoted
D6's corrected 0.0063, the committed analysis log carried the wrong figure, and
a regression test asserted it. Nobody re-read the code after writing the
correction. It was found on 6 October 2026 while refactoring an unrelated
function, by inspection and not by any check in this protocol. And the
pre-registration gives the measured advantage of extending a grid on random
labels over real ones as **five to seven times**, which is the
polynomial-kernel figure: on the RBF kernels the ratio is 2.0 and 35.7, so two
of the four measurements fall outside the stated range, one above it and one
below. Week 3 had the full four-row table in front of it when that sentence was
written. **This fourth one differs in kind from the three before it**, and the
difference does not favour it: those asserted things nobody had checked, while
this took a measurement that had been made correctly and stated it more broadly
than it supported. Nothing in a reader's view distinguishes a generalised
measurement from a measured one. The rule that figure supports is unaffected,
the direction holding on every kernel and both datasets; D17 records it and the
registered document is not edited.

**None of the seven is an audited pipeline failing an audit.** A reader who takes
this section as evidence that audited work fails these checks has read it as it
was first written and not as it is meant. The two kinds matter differently: the
first says the instrument needed repair, the second says its authors committed
the error the instrument exists to prevent.

**A further item, about Tier 2 rather than about either kind.** On a partial
sample of two of the six foreign Grams, the conditioning check read 1.7e+04 —
**understating the worst case by a factor of 26**. Two things should be kept
apart here. The numerical miss was corrected only by running the full six. What
printing the sample count achieved was narrower: it exposed that coverage was
incomplete, so the reading was known to be partial. **It did not establish the
true worst case and could not have.** That is the honest limit of indicative
sampling, and it argues for treating `--hook-sample` readings as a prompt to run
the full analysis rather than as a figure.

**A bounded gap the fifth item exposes, and two more beside it.** The superseded
bound was found by inspection, not by a check. So were two latent defects in this
project's own reporting code, found the same day: a Holm family size printed as
the literal 4 rather than computed, and a table headed "all cells" that silently
skipped cells with too few paired series. Neither of those two ever produced a
wrong value, so neither joins the count above; the superseded bound did, so it
does. The sixth item above, the grid adjudicator, was found the same way. What
all four share is the route. **Tier 1 reads records and Tier 2 reads kernels.
Nothing in this protocol reads this project's own analysis and reporting code
for claims the data does not support**, which is where all four lived.

**What now exists, and what it would not have caught.** Since 19 October 2026
`scripts/check_paper_figures.py` re-derives figures this paper prints from the
stored records, and a test asserts that the exclusion bound
`scripts/primary_tests.py` prints matches the copy `scripts/audit_sweep.py`
checks against regenerated data. Neither is part of the protocol, and the
figures check would have caught **none of the four items above**. All four were
divergences between code and record in which this paper's prose was correct or
unaffected: the fifth repair had `primary_tests.py` printing 0.0059 while every
document here quoted 0.0063, so a check reading the paper against the records
would have passed it without comment. What would have caught it is the narrower
assertion, the one tying a printed figure to the copy that is checked against
data — which exists only because the fifth repair was corrected at its value and
not at the structure that produced it. §4.7 states how much of this paper the
figures check covers, which is very little.

**A further group found by reading and deliberately not counted.** Three
separate generators defaulted to not recording their output: the `.docx`
exporter wrote no provenance, `scripts/exploratory_sweep.py` required `--out`
with no default, and the paper existed only as section files until an assembler
was written for it. An unrecorded output is an absent value rather than a wrong
one, so none of these joins the count above. One of them did publish a stale
artefact: on 15 October 2026 `docs/deviations.docx` was sixteen days and roughly
1,400 record lines behind its source, because generating the document was a step
somebody had to remember. `scripts/check_docx_fresh.py` now stores the SHA-256
of each export's source and fails when it moves. **It does not hash the
generator**, so a change there leaves every export reported current while its
output would differ, and **it does not look inside the document**, so an export
edited by hand after generation also reports current. Both gaps are stated here
rather than closed.

That last fact is the honest summary of what this protocol is worth. **A green
test suite was not evidence that a measurement tool measured anything**; reading
a report on real data was. Any reader adopting these checks should expect the
same, and should treat the first run against their own data as a test of the
checks rather than of their pipeline.

---

## 5.7 The one claim made without qualification

A results file in the format of 5.2 can be audited by a stranger in seconds,
without the pipeline that produced it, and the audit will say which questions
the file cannot answer. That is a property of the format, not of this project's
judgement, and it is the part that does not depend on trusting anything written
above.
