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
went wrong here, usually after passing review. Fifteen deviation records and a
list of caught mistakes are **not** evidence that a tool catches a stranger's
mistakes. They are evidence that this project eventually noticed its own.

**The prospective evidence is one case.** In week 6 the audit was run against a
foreign pipeline — Kakavand et al.'s six `ibm_fez` hardware Grams, condition
number 4.5e+05, read through an adapter against their public Zenodo deposit.
That is the only time these checks met records they were not designed around.
Parts B and C add two more cases apiece, but both were performed by the same
party that wrote the procedures.

**The protocol has failed its own standard, repeatedly, in public.** It asserted
from the manuscripts that two published benchmarks performed none of five
checks; when the deposit behind one was actually read, six of seven claims in
that paragraph were wrong or misleading. On its first contact with real records
it required a field this project's own pipeline never emitted, collapsed fifteen
configurations into one, and silently changed three answers. It then declared
four checks unrunnable when three were not — one needed nothing at all. The
first audit run against real records found four further defects, **all four in
the checks rather than in the records**, with the full test suite passing on
every one.

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
