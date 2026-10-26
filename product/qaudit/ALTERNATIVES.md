# What else does this, and what it means for the claim

Written 26 October 2026, because the README said no comparison had been done
and that is not a position to ship from. **The result narrows what can honestly
be claimed here.**

This is a search, not an exhaustive survey. It covers the two categories a
reasonable reader would raise and the quantum-specific work, and it names what
it did not look at.

## The uncomfortable finding first

**The content of these checks is not novel. It is a published consensus
standard.** REFORMS (Kapoor et al., Princeton) is 32 items across 8 sections of
reporting standards for machine-learning-based science, field-agnostic and
consensus-based. Its sections include **data leakage**, **metrics and
uncertainty quantification**, **modelling**, **computational reproducibility**
and **generalizability**, which is most of what the fifteen checks here are
about. Data leakage is the negative control. Metrics and uncertainty is chance
correction, the precision floor, statistical power and multiplicity.
Generalizability is the boundary-of-claims language this tool prints.

So the defensible claim is not "these are the things to check". Somebody else
established that by consensus and published it. The claim is narrower: **a
subset of it can be computed from a results file, and the remainder reported as
unanswerable with the missing field named.** REFORMS has no executable
implementation; it is used manually, by authors self-assessing, referees asking
for a completed checklist, and journals requiring one at submission.

That is a real difference and a modest one, and it should be stated as the
modest version.

## The closest thing in method, in another field

**statcheck** (R package, Nuijten et al., Tilburg) reads a manuscript, finds
null-hypothesis test results reported in APA style, recomputes each p-value from
the reported test statistic and degrees of freedom, and flags disagreement. It
distinguishes an inconsistency from a *decision error*, where the reported and
recomputed p-values fall on opposite sides of significance.

**It is the same shape as this tool and a narrower scope.** Its own
documentation says it "merely detects whether a set of numbers is consistent
with each other" and makes no claim about whether an analysis was appropriate or
a study valid. It finds a number that is wrong. This tool finds a number that is
**missing** and says which claim that kills. Those are different outputs and
neither subsumes the other.

**What statcheck does that this does not, and it matters commercially.** It
reads PDFs and HTML. It works on what a reader actually has in front of them,
which is a manuscript, and that is a large part of why it was adopted at all.
This tool requires a structured JSONL file that somebody has to produce, and the
one external deposit it has been run against needed 171 lines of bespoke adapter
and could still only supply 3 of 7 required fields. **On the evidence of
statcheck's adoption, the highest-value thing to build next is not more checks.
It is accepting what the person holding the claim actually has.**

## The quantum-specific work

**Bowles, Ahmed and Schuld, arXiv:2403.07059**, the paper this project cites as
reference [5]. They released `qml-benchmarks`: 12 quantum classifiers, classical
baselines, 160 binary classification datasets across 10 benchmarks, and
hyperparameter and cross-validation tooling on JAX and scikit-learn. It is a
**benchmark suite** and does not read or check anyone else's results file. They
identified the failure modes this tool checks for, including dataset
sensitivity, the benchmark lottery, positivity bias and unequal baselines, by
running their own benchmarks rather than by auditing published ones. Their
sample of 55 arXiv papers containing "quantum machine learning" and "outperform"
found about 40% claiming a quantum model beats a classical one and three
reporting the reverse.

**Metriq** and the **Quantum Benchmark Zoo** are catalogues: platforms for
submitting, tracking and browsing benchmark results and benchmark definitions.
Neither assesses what a submitted result can support.

**QED-C benchmark suites** are, likewise, suites to run rather than tools to
read someone else's output.

## Where that leaves the claim

[Certain] Nothing found takes a third party's results file and reports its
evidential reach: which claims it supports, which questions it cannot answer,
and which field's absence blocks each one. REFORMS says what to report and does
not compute. statcheck computes and asks a different question, in another field,
about numbers that are present rather than absent. The quantum work builds
suites and catalogues.

[Likely] The gap is real and it is narrow. It is a gap in **form**, not in
content: an executable that reads a file and reports refusals, where the
discipline already has a consensus checklist and a manuscript-level
consistency checker.

[Guessing] The gap persists because the input does not exist. A checklist needs
no input and a PDF checker needs a PDF; this needs structured records that
nobody currently has a reason to emit.

## What this changes in the README

The line saying no comparison has been done is replaced by a pointer here. No
uniqueness claim is made. The README does not say this tool is the only thing
that does what it does; it says what was looked at, what was found, and that the
check content is a consensus standard rather than an invention of this project.

## What was not looked at

Model cards, datasheets for datasets and Croissant-style metadata, which
describe artefacts rather than assess claims. Experiment trackers such as MLflow
and Weights and Biases. The p-curve, GRIM and SPRITE family, which test
distributions of published statistics across literatures rather than one file.
Governance frameworks including the NIST AI Risk Management Framework, ISO/IEC
42001 and EU AI Act conformity assessment, which operate at the level of an
organisation's process. Any of these could change the picture and none was
examined.

## Sources

* REFORMS, https://reforms.cs.princeton.edu/
* statcheck, https://cran.r-project.org/package=statcheck
* Bowles, Ahmed and Schuld, https://arxiv.org/abs/2403.07059
* `qml-benchmarks`, https://github.com/XanaduAI/qml-benchmarks
* Quantum Benchmark Zoo, https://quantumbenchmarkzoo.com/
