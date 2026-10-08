# Section 1 — Introduction

A quantum-classical kernel comparison can be run carefully, pass every test its
authors wrote, and still not support the claim made from it. The ways such a
comparison fails are mostly not visible in its results: a metric compared across
two different nulls, a difference below the arithmetic resolution of the
pipeline, power measured on the wrong pairs, an asymmetric quantity carried into
code with its arguments the wrong way round. None of these shows up as an error.
Each shows up as a number.

This paper is about what a published artefact lets a reader establish, worked
through a pre-registered comparison that was built to answer a different
question and, in answering it, kept finding that the question behind it was
whether anyone could check.

---

## 1.1 The registered question

Huang et al.'s geometric difference is used as a screen: compute a cheap
quantity from two kernel matrices before training, and learn whether a quantum
kernel could outperform a classical one on this data. The practitioner's version
is narrower and more useful — can a cheap number tell me **not to bother**?

This study registered that question on imbalanced business tabular data, where
the claim matters commercially and where the literature's benchmarks mostly are
not: Telco customer churn and credit-card fraud, 360 pre-registered units across
three feature mappings, five qubit counts, three training sizes and four quantum
settings, twenty seeds each.

---

## 1.2 What this paper reports

**A screen that is not usable, within its tested scope.** On those 360 units the
registered decision rule returns no verdict, because no regularisation column is
free of ceiling breaches under any of three λ rules evaluated — a rule declining
to speak, not a finding that no relationship exists. The third of those rules is
the one Huang's own source prints, and it turned out not to select a λ at all on
**76.5%** of the units: on 81.3% of them his λ rule and his √N ceiling cannot
both be satisfied. Neither this study nor the peer-reviewed paper that inherited
the quantity had ever run it. At λ = 0.1, the only column where all 360 units survive, the
null *is* rejected and in the predicted direction: rho = +0.17, p = 1.1e-03. That
relationship accounts for **under three percent of the rank variance** and
**reverses sign** across the regularisation sweep — to −0.38 at λ = 1e-3 — so what
it appears to say depends on a parameter the practitioner chooses. A quantity
explaining three percent of rank variance, whose sign moves with a free parameter,
cannot tell a practitioner not to bother. Alongside it, no quantum advantage at
either primary cell: on churn a measured classical advantage, on fraud an
exclusion bound.

**An audit procedure that separates three things published work routinely
merges**: a measurement, a refusal, and an unsupported claim. A measurement
says what a quantity is. A refusal says the file cannot answer a question and
names which. An unsupported claim is an assertion its own artefact does not
license. The procedure's output is mostly refusals, and the paper is explicit
that a refusal is not a finding about the audited work.

**A record format whose value is a property of the format.** A results file
carrying the fields in §5.2 can be audited by a stranger in seconds, without the
pipeline that produced it, and the audit states which questions that file cannot
answer. This is the one claim here made without qualification.

**Source-to-implementation checking, with results.** Reading two papers at
source rather than in rendering, and comparing against their released code,
established that an asymmetric quantity is introduced in an appendix with its
arguments reversed relative to the main text and without relabelling, and that
the reversal propagates into a peer-reviewed paper whose equation, code and
stated interpretation all agree with one another. Applied to this project
itself, the same procedure established that **every one of its 15,120 result
records stores a code identifier no reader can resolve**.

---

## 1.3 What this paper does not claim

Stated here rather than left to the discussion, because each is a claim a reader
might reasonably expect and none is supported.

**Not that the geometric difference is invalid in general.** It was measured on
one grid, with one treatment of its regularisation parameter, on two datasets,
one of which is saturated at every training size tested. A quantity can be
uninformative where it was measured and informative elsewhere, and nothing here
separates those cases.

**Not that it carries no signal.** At the one breach-free regularisation column
the relationship is statistically detectable and runs in the predicted direction.
The claim above is about usability — an effect of that size, with that sign
instability, cannot support a go/no-go decision — and not about absence.

**Not that the audit detects defects in other people's pipelines.** On the one
occasion these checks met records they were not designed around, they produced
one measurement and eight refusals and **found no defect, nor were they looking
for one**. Whether they would detect an error in unfamiliar work is, on one
case, unevidenced either way.

**Not that the protocol is validated.** Every records-level and kernel-level
check was written after the defect it catches. The instrument has needed repair
five times in public, twice because the tool was wrong and three times because
its authors asserted something they had not checked. The fifth was a superseded
exclusion bound that the confirmatory script printed for eleven days after the
correction was written, pinned in place by a regression test; nothing in the
protocol caught it, because nothing in the protocol reads this project's own
reporting code.

**Not that the findings about published work are errors in their conclusions.**
They are statements that a claim cannot be checked from the published artefact
without going to source. In the orientation case the ambiguity originates
upstream of the authors who inherited it.

---

## 1.4 How to read this

Section 2 establishes what the geometric difference is, what its bound does and
does not assert, and how its arguments compose — the derivation the rest
depends on. Section 3 traces the registered design and marks every subsequent
amendment. Section 4 reports the results. Section 5 is the protocol: what is
tooling, what is a reading procedure, what each costs, and §5.6, which argues
against the contribution. Section 6 bounds what all of it supports. Section 7
points at the deviation records, which govern wherever they and the
pre-registration disagree.

A reader with limited time and a sceptical disposition should read §5.6 and
§6.3 first. They are where this paper says what its evidence will not carry.
