# Section 6 — Discussion

**Draft, 10 October 2026.** Limitations are in §4.7 and are not repeated here.

One distinction runs through this section and is stated once at the top because
everything else depends on it. **Refusing an unsupported conclusion and
detecting a defect are different operations.** The first says a file does not
license a claim. The second says something in the work is wrong. This project
performed the first many times and the second rarely, and conflating them would
inflate every result below.

---

## 6.1 A null, within a stated scope

**What was found.** No quantum advantage on either dataset at the pre-registered
primary cells. On churn the result is stronger than a failure to detect: both
endpoints reject and both favour the classical kernel, a median deficit of
0.0659 normAP in the cell chosen because the classical baseline was strongest
there. **The margin is narrow and §4.2 states it:** the effect clears that
cell's *true* minimum detectable effect of 0.0608 by **1.31x**, not the
registered 0.0171 it appears to clear by 4.7x, and D6 withdraws any phrasing
that reads as comfortably powered. On fraud the test does not reject, and is reported as a bound — an
advantage larger than 0.0063 normAP at that cell is excluded at 80% power.

H2 and H3 return NOT ESTABLISHED under the registered decision rule. **That
verdict is the rule declining to speak, not a finding that no relationship
exists**: no λ column is free of ceiling breaches, so none satisfies the
registered precondition. **Three λ rules have now been evaluated** — the frozen
sweep {1e-1, 1e-2, 1e-3, 1e-4}, the corrected C-derived rule λ = 1/(2C), and
Huang's own g_tra selection over his declared grid, specified in advance in D16.
**The third did not fail to produce a clean column so much as fail to produce a
column**, for the reason in §6.2a, and is reported as unresolved rather than
negative. At λ = 0.1, the only column where all 360 units survive,
the null *is* rejected and in Huang's predicted direction — rho = +0.1712,
p = 1.11e-03, CI [+0.069, +0.270]. The substantive figure is therefore neither the
verdict nor the sign but **rho² = 0.0293**: the geometric difference accounts for
under three percent of the rank variance in observed difference.

**The scope that result lives in.** Two datasets, one of which is saturated at
every training size this study used. Three feature mappings, five qubit counts
from 4 to 12, three training sizes from 50 to 250 per class, two embeddings at
one and two repetitions, statevector simulation on `lightning.qubit`, no
hardware. Twenty seeds resampled from one fixed dataset each, which the
registration recorded in advance as mildly anti-conservative on fraud.

**What this does not establish.** It does not establish that the geometric
difference is generally invalid as a pre-training screen. It was measured on
this grid, with this λ treatment, against these kernels, on these two datasets.
A metric can be uninformative where it was tested and informative elsewhere, and
nothing here distinguishes those cases. **The defensible claim is that on 360
pre-registered units of imbalanced business tabular data, g is not usable as the
screen it is offered as** — a detectable relationship carrying under three percent
of rank variance, whose sign depends on a parameter the practitioner chooses,
cannot tell anyone not to bother. That is a meaningfully powered negative result
about the screening use of the quantity. It is not a claim that the quantity
carries no signal, and not a claim about the quantity in general.

Two features of the result deserve weight a reader might otherwise give the
verdict. The relationship **reverses sign across the regularisation sweep**,
from +0.17 at λ = 0.1 to −0.38 at 1e-3, so g's apparent relationship to
performance depends on a parameter the practitioner chooses. And the columns at
small λ exclude most units for breaching their own ceiling, so the strongest
correlations are computed on the most heavily selected populations.

---

## 6.2 Limits on auditability, which is what the checking found

Three bodies of work were read at source and compared against their
implementations, and in each case the artefact was internally consistent while
the claim about it was not checkable from what had been published.

In Huang's appendix, a regularised quantity is introduced whose ordered
arguments are the reverse of the main text's, without being relabelled. In
Flórez Ablan et al., that reversal propagates: their equation, their code and
their stated interpretation agree with one another, and the quantity they
compare against √N is the reverse of the screening quantity. In their released
code, ROC-AUC is computed from hard predicted labels, and `g_tra` — the
diagnostic their own source quotes as the condition under which g is meaningful
— is computed throughout and never compared to anything.

**None of these is reported here as an error in their conclusions.** Each is a
statement that a published claim cannot be checked from the published artefact
without going to source, and in the orientation case the ambiguity originates
upstream of the people who inherited it.

Turned on this project, the same procedure found that **every one of 15,120
result records stores a commit identifier that no reader can resolve**. The
limitation is bounded and specific: a reader cannot bind a historical record to
the code that produced it. Everything else — the scripts, the data checksums,
the records — remains checkable, and a re-run from current code produces new
evidence rather than authenticating the old.

The common shape is worth naming. In all four cases nothing was internally
inconsistent, and in all four cases a reader working from the public artefact
alone could not have established what they would have needed to. **That is the
auditability limit this study demonstrates**, and it is a limit on what
published materials support, not a finding about anyone's competence.

---

## 6.2a Running the source's own λ rule, which neither group had run

Reading at source is what found the three items above. Running what the source
printed produced something different in kind: not a limit on what can be
checked, but a measurement of the method.

**Source states** that g_gen is reported at the largest λ in the declared grid
{1e-5, 1e-4, 1e-3, 1e-2, 0.025, 0.05, 0.1} such that the training error
g_tra ≤ 0.045. **Neither group had run it.** Flórez Ablan et al. compute g_tra
throughout their pipeline and never compare it to anything; this study did not
compute it at all, substituting a λ derived from the classical arm's C, as they
also did, and neither group said so. The procedure was specified in full and
published before it was computed, including its outcome-to-verdict mapping and a
proof of what the outcome could not be.

**What it gives on 7,200 units.** On **5,507 of them, 76.5%, no λ in the grid
satisfies the threshold at all.** Of the 1,693 that admit one, 348 then put g_gen
above its own √N ceiling. **So on 81.3% of the units the source's λ rule and the
source's ceiling cannot both be satisfied**, and 1,345 units satisfy both.

The two constraints bound λ from opposite sides, which §2.3 states from the
source. This measures the cost of that on imbalanced business tabular data, and
the shape is specific: **all 348 breaching rows selected one of the two smallest
grid values, and no row selecting λ ≥ 1e-3 breaches**. The rows where the g_tra
rule permits only a tiny λ are exactly the rows where the ceiling then fails.

Inadmissibility is uniform rather than concentrated: between 68.9% and 80.6%
across every (dataset, qubit-count) combination, and comparable across training
sizes and feature mappings. It is a property of this data against this rule, not
of one corner of the grid.

**What this does not claim.** Not that the rule is unsatisfiable in general: it
was measured on two datasets, one grid, one orientation, statevector simulation
and this study's classical kernels. Not that g_gen is therefore unusable, which
§6.1 settles separately and on different evidence. And not a verdict on H2 or
H3, which stay NOT ESTABLISHED; a rule that declines to select a λ leaves the
registered decision rule with nothing to read, which is why this is reported as
unresolved rather than as a negative result.

---

## 6.3 What the evidence supports about the protocol itself

Little, and the honest accounting is short.

**The record format's value is demonstrated, by a stated criterion.** Applied to
a foreign deposit, it produced one measurement and eight refusals in seconds
without the originating pipeline. The criterion is whether a reader's knowledge
of what that deposit can support changes: before the run they could not say
which questions those records answered, afterwards they could. That is met.

**The checks' prospective defect-detection is not demonstrated.** On the only
occasion they met records they were not designed around, **they found no defect
and were not looking for one**. Eight refusals are eight refusals — the
instrument declining to answer — and not eight findings about the audited work.
Reading them as the latter is precisely the conflation this section opened by
naming.

**The retrospective instances are weak evidence.** Every records-level and
kernel-level check was written after the defect it catches. Sixteen deviation
records show that this project eventually noticed its own mistakes; they do not
show that a tool built from them catches a stranger's.

**And the instrument has needed repair.** Four things have gone wrong in public:
two defects in the tool, including a first run on real records whose four
defects were all in the checks with the full suite passing; and two claims its
authors made without checking, including one paragraph about published
benchmarks of which six of seven claims were wrong. A green test suite was not
evidence the instrument measured anything; reading a report on real data was.

**One prospective check of the audit trail did succeed, and its significance is
narrow enough to state exactly.** On 1 October 2026, before any value was
recomputed, this project published an analytical upper bound on the effect of
correcting its λ-from-C rule: from the monotonicity of g in λ, at least 5,710 of
7,200 rows would be ceiling-free under the corrected rule and **at most 1,490
could still breach**. The correction was adopted and pushed with its full
outcome-to-verdict mapping before the recomputation ran. The recomputation
produced **979** breaches, inside the published interval, and the four λ columns
that should not have moved came back bit-identical across six days and a separate
run.

**What that demonstrates, precisely.** That a quantitative prediction about this
pipeline's own behaviour was recorded publicly in advance and the computation
satisfied it. It is evidence for the **audit trail and the internal consistency
of the computation** — that the stored records, the stated monotonicity and the
re-run agree, and that the ordering of declaration and result is checkable rather
than asserted.

**What it does not demonstrate, and the distinction matters more than the
result.** It does not validate the geometric difference as a predictor, because
the bound is a statement about ceiling arithmetic and not about g's relationship
to performance. It does not establish H2 or H3, which remain NOT ESTABLISHED. It
is not prospective defect detection: the prediction was confirmed, so no defect
was found, and a satisfied bound is the absence of a surprise rather than the
presence of a finding. And it concerns this project's own pipeline, not a
stranger's, so it does not touch the gap named above.

So the claim is narrow. **A results file in this format can be audited by a
stranger in seconds, and that is a property of the format.** Whether these
particular checks detect errors in work they were not designed around is, on one
case, unevidenced either way.

---

## 6.4 What would change these conclusions

**For the null:** a dataset where the classical baseline is not saturated and
the quantum kernel has headroom to climb; hardware records rather than
statevector simulation; and a λ treatment settled from source rather than from
the unsourced rule this project used for its supplementary column. The first of
these matters most. Fraud is saturated at every training size tested, so one of
two datasets could not have shown an advantage had one existed.

**For the protocol:** application by someone who did not write it, to data they
did not choose, looking for something they did not already know was there. That
is the experiment this project cannot perform on itself, and until it is done
the protocol's prospective value rests on one case that found nothing and said
so.

---

## 6.5 What this study is for

The registered question was whether a cheap pre-training screen tells a
practitioner not to bother. On the units tested, it cannot: g carried under three
percent of the rank variance, and its sign depended on a regularisation parameter
the practitioner picks. A relationship detectable at one column is not a screen.
That is useful to know and it is bounded by the grid it was measured on.

The more durable contribution is probably the smaller one. **A comparison can be
run carefully, pass its own tests, and still not support the claim made from
it** — and the difference is visible in whether the file it produced lets someone
else check. This study's own records failed that test for nine days before
anyone looked, which is the strongest argument in it for the format and the
weakest possible endorsement of the judgement that produced it.
