# Section 2 — Background: the geometric difference and its ordered arguments

**Draft, 3 October 2026.** Written under the framing recorded in D15.

This section states what the geometric difference is, what Huang's bound does
and does not claim, and what happens to both when an asymmetric quantity is
carried from a paper into code. Throughout, three things are kept apart and
labelled: **what a source states**, **what an implementation does**, and **what
this project verified by comparing them**. That separation is not stylistic.
The errors this section documents live exactly in the gap between the three.

---

## 2.1 The quantity

Huang et al. introduce the geometric difference to answer a question about
*model complexity* rather than about accuracy: given a function a model with
kernel K¹ can represent, how much complexity does a model with kernel K² need
to reproduce it?

**Source states** (arXiv:2011.01938, read from the e-print LaTeX; see 2.6 for
provenance). Equation (5):

> g(K¹ ‖ K²) = sqrt( ‖ sqrt(K²) (K¹)⁻¹ sqrt(K²) ‖_∞ )

with ‖·‖_∞ the spectral norm and the normalisation tr(K¹) = tr(K²) = N, N the
number of training samples. The accompanying bound is

> s_{K¹} ≤ g(K¹ ‖ K²)² · s_{K²}

where s_K is the model complexity under kernel K.

Three properties follow from the printed definition and matter for everything
after.

**It is asymmetric.** The inverse falls on the first argument and the outer
square roots on the second. g(K¹‖K²) and g(K²‖K¹) are different numbers, and
nothing in the notation prevents one being used where the other is meant.

**It is a necessary condition, not a sufficient one.** Source states: *"if the
geometric difference is small, then a classical ML method is guaranteed to
provide similar or better performance"*, and *"if g_CQ is large we show that
there exists a data set with s_C = g²_CQ s_Q"* with the quantum model
performing better. A large g establishes that **some** dataset exists on which
the quantum model wins. It does not establish that any particular dataset is
such a dataset.

**It is bounded.** With the trace normalisation above, g cannot exceed √N. A
value above that ceiling reports that the inverse is under-regularised, not that
the kernels are far apart.

The screening quantity is therefore **g(K_C ‖ K_Q)** — classical first, so the
classical kernel is the one inverted — and it must be large for a quantum
advantage to be possible at all.

---

## 2.2 The regularised form, and a reversal inside the source

An exact inverse is unusable on an ill-conditioned Gram matrix, so the
regularised form is what anyone computes.

**Source states.** Appendix F, Equation (F19):

> g_gen = sqrt( ‖ sqrt(K¹) sqrt(K²) (K² + λI)⁻² sqrt(K²) sqrt(K¹) ‖_∞ )

and (F20):

> g_tra = λ · sqrt( ‖ sqrt(K¹) (K² + λI)⁻² sqrt(K¹) ‖_∞ )

**The regularised inverse is on K², the second argument. In Equation (5) it was
on the first.**

**This project verified** that this is not an inconsistency. Appendix F poses
the reverse operational question — given a function represented by kernel 1,
what complexity results when kernel 2 is trained to reproduce it — and derives

> s_{K²} ≤ g_gen² · s_{K¹}

so that, at λ → 0, g_gen = g(K² ‖ K¹). The ordered comparison is reversed
between the main text and the appendix, deliberately and for a stated reason.

**What is nonetheless true of the notation.** The appendix presents F19 as the
regularised geometric difference and does not relabel it as the reversed
comparison, while the main text directs the reader to the appendix for the
detailed derivation. A reader who takes F19 as "the regularised Equation (5)"
and substitutes K¹ = K_C, K² = K_Q obtains the reverse of the screening
quantity. **That is the trap this section exists to document**, and it is not
hypothetical: section 2.4 shows it closing on a peer-reviewed paper.

---

## 2.3 What λ is, and what it is not

**Source states.** Huang reports g_gen *"with the largest λ such that the
training error g_tra ≤ 0.045"*, selected from the grid
{1e-5, 1e-4, 1e-3, 1e-2, 0.025, 0.05, 0.1}. **This project verified** that the
source is internally inconsistent on the boundary, writing ≤ 0.045 in one place
and < 0.045 in the numerical-details passage; exact equality is unlikely to
bind in floating point, and the discrepancy is recorded rather than resolved.

**g is not a property of a kernel pair.** It is a property of a kernel pair *and
a λ*. The two constraints pull in opposite directions: g_tra increases with λ,
so the ≤ 0.045 rule bounds λ from **above**, while an unregularised inverse
drives g over its √N ceiling, which bounds λ from **below**. Reporting a g
without its λ is reporting an incomplete quantity.

**Source states no relation between λ and an SVM's C.** Huang prints no
SVM-to-kernel-ridge correspondence. The only λ-bearing objective is Appendix D's

> min_w [ λ⟨w,w⟩ + Σ_{i=1..N} (residual_i)² ]

a plain sum, not a mean. **This project verified** the consequence: normalising
an SVC primal (1/2)‖w‖² + C·Σ loss so the per-sample loss carries coefficient 1
gives λ = 1/(2C) against a summed risk and λ = 1/(2CN) against a mean risk.
Which is correct depends on the objective the λ belongs to, and Appendix D's
summed form points to 1/(2C). **Neither is Huang's procedure**, which selects λ
by the g_tra rule and not from C at all.

---

## 2.4 Source against implementation

The checks below are the ones this project's protocol specifies. They are
reported here because they are the worked example that motivates it.

### Flórez Ablan, Roth and Schnabel (2025)

**Source states** (arXiv:2503.05602, read from the e-print LaTeX). Their
Equation (4) is F19's structure — regularised inverse on K₂, outer roots K₁ —
cited to Huang. Their line 213 assigns **K₁ = K_C and K₂ = K_Q**. Their
interpretation follows Huang's main text exactly: *"only if g(K_C, K_Q) ∝ √N
holds, the necessary condition for potential quantum advantage is fulfilled"*,
and for values below that line, *"we are guaranteed that the classical model
provides similar or better performance"*. Their λ is **1/(2C)** with
C ∈ [32, 1024]; no g_tra rule appears anywhere in the source.

**Implementation does.** Their released code calls
`geometric_difference(K_train_poly, K_train_quantum, 1/(2*C_quantum))`, faithful
to their Equation (4). Paper, equation and code agree with one another.

**This project verified, by composition.** Since F19's g_gen is g(K²‖K¹), and
their assignment is K¹ = K_C, K² = K_Q, the quantity they report as g(K_C, K_Q)
and compare against √N is Huang's **g(K_Q ‖ K_C)** — the reverse of the
screening quantity.

**Stated as scope rather than as accusation.** Their reading of F19 is the
natural reading of an appendix that presents it as the regularised Equation (5).
The ambiguity originates upstream. What follows is that a g from their pipeline
and a g from any pipeline using Equation (5)'s orientation are reciprocal
quantities and cannot be compared without first fixing the ordering.

Two further observations from their released code, relevant to what a published
number means. Their ROC-AUC is computed on hard predicted labels —
`decision_function` and `predict_proba` do not occur in the repository — which
makes the reported quantity balanced accuracy rather than a ranking measure.
And `g_tra` is computed and stored throughout their pipeline and never compared
to anything; the 0.045 threshold appears once, in a docstring quoting Huang, and
is never applied.

### This project

**Implementation does.** `geometric_difference_regularised(K_C, K_Q, lam)`
computes

> sqrt( ‖ sqrt(K_Q) sqrt(K_C) (K_C + λI)⁻² sqrt(K_C) sqrt(K_Q) ‖_∞ )

which is F19 with K¹ = K_Q and K² = K_C, hence g(K_C ‖ K_Q) — the screening
quantity.

**Stated without credit-taking.** The orientation is correct, and no record from
the weeks in which it was written shows that the reversal in Huang's appendix
had been identified at the time. It was established on 1 October 2026, after
every g in this project had been computed. The implementation is right; the
reasoning for it was reconstructed afterwards, and the paper says so rather than
presenting the outcome as foresight.

**And one of this project's own rules is unsourced.** Its λ-from-C helper
returns 1/(2CN) with a docstring asserting the correspondence and citing
nothing. Against Appendix D's summed objective that is probably wrong by a
factor of N. The frozen λ sweep that carries every reported result is unaffected;
the λ-from-C column is not, and the correction is recorded as an undecided
deviation rather than applied in passing.

---

## 2.5 Two algebraic facts that change how g reads

**This project verified** both; neither is stated in the sources consulted.

**g(K, K) ≠ 1.** For a kernel compared with itself, the regularised form gives
μ_max/(μ_max + λ). So "g ≈ 1 rules advantage out" has a λ-dependent floor below
one, and a g near unity is not evidence of kernel identity.

**The classical factor is capped at 1/(4λ) for any kernel whatsoever.** With
A = sqrt(K_C)(K_C + λI)⁻² sqrt(K_C), A's eigenvalues are μ/(μ+λ)², maximised at
μ = λ where the value is 1/(4λ). Hence g ≤ sqrt(‖K_Q‖_∞ / (4λ)), and with K_Q
normalised to trace N a breach of the √N ceiling requires

> ‖K_Q‖_∞ / N > 4λ

— more than 40% of the quantum Gram's trace in a single eigenvalue at λ = 0.1,
4% at 1e-2, 0.4% at 1e-3. Verified across 960 sampled observations: the bound is
violated zero times.

The consequence for reading any reported g: a large value at small λ is
compatible with the classical kernel being badly conditioned relative to λ, and
says nothing on its own about the quantum kernel.

---

## 2.6 Provenance of the sources used here

Every statement labelled "source states" above was read from the arXiv e-print
LaTeX, not from a PDF rendering, a publisher's HTML, or any model's
transcription of either.

| source | archive SHA-256 | main file SHA-256 |
| --- | --- | --- |
| Huang et al., arXiv:2011.01938 | `b510654c6628…` | `maintext.tex` `ceded212c4b0…` |
| Flórez Ablan et al., arXiv:2503.05602 | `7ce99d754ecc…` | `main.tex` `1903926fe4b5…` |

This matters because earlier attempts in this project to obtain Huang's Appendix
F from rendered PDFs returned transcriptions that were **internally
contradictory on exactly the subscripts in question**, and one claim — that
Huang's appendix contradicts his own main text — was drafted on that basis and
withdrawn once the source was read. A claim about an equation's index placement
is only as good as the characters it was read from.

---

## 2.7 What this section establishes, and what it leaves open

**Established from source:** the definition and asymmetry of g; the bound's
status as necessary and not sufficient; the √N ceiling; the reversal between
Equation (5) and F19 and the reason for it; Huang's λ rule and its boundary
inconsistency; Huang's summed objective; Flórez Ablan et al.'s equation,
assignment, λ and interpretation, and their code's fidelity to their equation.

**Established by this project's own analysis:** that their reported quantity is
the reversed comparison; g(K,K) = μ_max/(μ_max+λ); the 1/(4λ) cap and the
resulting breach condition; that this project's own λ-from-C rule is unsourced.

**Left open:** whether 1/(2C) or 1/(2CN) is correct for this project's purposes,
and what follows for its λ-from-C column; both are recorded as an undecided
deviation and neither is used to revise any frozen analysis.
