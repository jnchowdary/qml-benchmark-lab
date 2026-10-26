# Validation notes

Observations that bear on whether this tool's output can be trusted, kept here
rather than in the paper, which is closed. Nothing in this file amends a
deviation record.

## A recurring overstatement: a verdict line claiming more than its number supports

**Three instances, and the third makes it a pattern rather than three
accidents.** All three had a correct verdict rule and a sentence beside it that
the number did not support. None was caught by a test.

1. **The registered grid adjudicator printed a withdrawn verdict for three
   weeks.** `scripts/check_grid_edges.py` compared the gain from widening a grid
   against a minimum detectable effect, a rule the week-3 record had already
   filed as a defect, and printed UNDER-TUNED on fraud where the registered
   comparison against a shuffled-label null returns adequate. The measurement
   was never wrong; the adjudication was absent from the code. Section 5.6 of
   the paper carries it as the third instrument defect.

2. **The negative control printed a sigma with no meaning.** Its verdict rule
   has always required both a sigma bar and the reproducibility floor, because
   the first version divided by a standard error of order 1e-22 and reported
   3.5e+16 sigma on a mean deviation of 0.000014. The PASS line printed the
   sigma regardless, and a healthy control is exactly when the figure is
   residue: the shipped template read `normAP -0.0000 (-479279874081.53 sigma)`.
   Fixed 25 October 2026; the line now gives the deviation, says it is inside
   the floor of its stated null, and says why no sigma is reported.

3. **The selection check described +0.098 as tracking the endpoint.** On the
   reconstruction demonstration it printed `rank correlation is +0.098, so
   selection is auditable and the criterion tracks the endpoint`. Fixed 26
   October 2026.

**The shape, stated so it can be looked for.** A check computes a number
correctly, applies a correct rule to it, and then describes the result in
language that implies a stronger finding than the number carries. A green test
suite cannot catch it, because the verdict is right. Only reading the printed
line against the number catches it, which is how all three were found: by
running the tool on real input and looking at the output.

**This is section 5.6's closing claim arriving a third time**, which says a
green check is not evidence that the thing it checks is right. The paper is
closed and this is not proposed as an amendment to it. It is recorded here so
that the next check written in this package is read against its own numbers
before it ships.

### The sign boundary in the selection check, and why the message now reports without judging

The check's verdict boundary is the **sign** of the rank correlation between the
inner selection score and the endpoint. A correlation that is not positive means
the criterion carries no information about the quantity it selects for, which is
a statement about direction and needs no threshold.

No magnitude threshold is used, deliberately. Any cut-off on how strongly a
criterion must track its endpoint would be chosen rather than derived, and a
chosen threshold presented as a verdict is the defect this protocol exists to
report. The cost of that choice is that a single PASS covers +0.001 and +0.999
alike, so the message now states the observed correlation, says that a positive
sign establishes only that an inner criterion existed and is not
anti-correlated with the endpoint, and says explicitly that **no assessment of
the strength of association or of statistical significance is made.**

### The other PASS messages, reviewed 26 October 2026

Every PASS line in `audit.py` was read against what its number supports.

**No change needed:** `schema` (reports which fields are present),
`chance correction` (states the chance level and that comparability holds within
the file and nowhere else), `pairing integrity` (fingerprints match, so pairing
is valid), `precision floor` (all differences exceed the declared floor),
`tuning symmetry` (reports observed variation per method),
`hardware cost claims` (the three fields are present, so a cost claim is
checkable). Each asserts what it measured.

**Reviewed and left, with the reason recorded rather than the wording changed:**

* `kernel conditioning` says the condition number "stays below 1e12, so the dual
  is well determined" on a **sampled** basis. The sample size and its coverage
  are named in the same sentence, and section 5.6 already carries the case where
  a two-of-six sample understated the worst case by a factor of 26. A reader is
  told what the reading rests on. Left as is.
* `multiplicity` returns PASS reading "0 comparison in this file" when a file
  holds a single method. Accurate, and arguably the question does not arise
  rather than being answered. Left as PASS because there is no multiplicity
  problem to declare, not because one was checked and cleared.

## Wall time is not QPU time, and a field can exist without a figure in it

From the Kakavand deposit, recorded because it is direct external evidence for
why `hardware cost claims` exists.

`hardware_metadata.qpu_seconds` reads **0.0 on all six hardware runs**. The code
that wrote it is not in the deposit, so its meaning is unresolved: it may mean
the metered figure was not captured, or something else. It is not read as zero
usage and `reconstruct_kakavand.py` deliberately does not emit it, because
writing 0.0 would assert a metered figure nobody has confirmed.

`wall_time_sec` across the same six runs spans **569.1 to 4435.2 seconds for an
identical workload** of 1,830 circuits at 1,024 shots. That spread makes wall
time unusable as a QPU-time estimate. **It does not identify how much of the
variation is queueing and how much is other overhead**, and the deposit contains
nothing that would separate them.

**This changes nothing in deviation record D18 and no amendment is proposed.**
D18's load-bearing claims are that the pairwise circuit count has no shot
dimension and that one primary-cell Gram is 116,300,800 Sampler executions
against a documented ceiling of 10 million per job. Neither depends on a rate.
D18's own 20-to-300-microsecond-per-shot bracket is labelled an estimate on
which no decision rests, and wall time is a different quantity, so the
observation neither confirms nor refutes it.

What it does support is the design of the cost check: a careful group deposited
a field for metered QPU seconds, it carries no figure, and the wall-clock number
beside it cannot substitute. A check that accepted either would report a cost
that was never measured.

## A claim that was true when written and is not now

Found 26 October 2026, by checking the package's description of itself after
three changes rather than assuming it had kept up.

`README.md` said the checks "and their wording are unchanged from that
repository's `scripts/audit.py`". That was true at extraction on 25 October and
false by 26 October. The package had diverged by 158 net lines across 14 hunks:
one added check, one verdict change in `schema`, and two corrected PASS
messages. `EXTRACTION.md` likewise asserted that `qaudit` gives the same report
as the research copy on the same input, where what is actually guaranteed is
agreement with the research repository's committed report **on the one external
file**, field for field.

Both are corrected in place. The research copy is deliberately not edited to
match: `scripts/audit.py` produced the results in the closed paper and §5.6
describes it as it stands.

**The shape, for the list above.** This is not a verdict line overstating its
number. It is a true statement left standing while the thing it described moved,
which no test can catch because nothing executes a README. The only defence is
re-reading a document's claims about itself whenever the thing it describes
changes, and that is now a step rather than an intention: each later change to
this package gets an entry in this file, and a change that alters a verdict or a
printed message gets its claim in README.md and EXTRACTION.md re-read in the
same commit.
