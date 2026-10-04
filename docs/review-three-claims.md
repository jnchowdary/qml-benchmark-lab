# Review of the three consequential claims

**4 October 2026.** Written in response to three questions, each of which found
something. Two of the three claims need changing before they go out; the third
needs a repair rather than a better sentence.

---

## Q1 — Equation composition: can a reader reproduce the mapping?

Not from section 2 as written. The conclusion is stated and the premises are
scattered. Here is the mapping explicitly, as it must appear in the paper.

### The chain

**Step 1 — source, Huang Eq. (5).**

    g(K¹‖K²) = sqrt( ‖ sqrt(K²) (K¹)⁻¹ sqrt(K²) ‖_∞ )      with      s_{K¹} ≤ g(K¹‖K²)² · s_{K²}

Read the pattern, not the letters: **the inverted matrix and the bounded
complexity are both the first argument.**

**Step 2 — source, Huang Eq. (F19) and its bound.**

    g_gen = sqrt( ‖ sqrt(K¹) sqrt(K²) (K² + λI)⁻² sqrt(K²) sqrt(K¹) ‖_∞ )    with    s_{K²} ≤ g_gen² · s_{K¹}

Here **the inverted matrix and the bounded complexity are both the second
argument.**

**Step 3 — the inference.** Eq. (5)'s template is `s_a ≤ g(a‖b)² · s_b`. F19
supplies `s_{K²} ≤ g_gen² · s_{K¹}`. Matching a = K², b = K¹:

    g_gen(K¹, K²) = g(K² ‖ K¹)

**Step 4 — source, Flórez Ablan et al. Eq. (4)** is F19's expression, and their
text assigns **K₁ = K_C, K₂ = K_Q**.

**Step 5 — their code.** `geometric_difference(K_train_poly, K_train_quantum, …)`
— classical first, quantum second, consistent with step 4.

**Step 6 — compose.** Their value = g_gen(K¹ = K_C, K² = K_Q) = **g(K_Q ‖ K_C)**.

**Step 7 — this project's code** computes

    sqrt( ‖ sqrt(K_Q) sqrt(K_C) (K_C + λI)⁻² sqrt(K_C) sqrt(K_Q) ‖_∞ )

Matched to F19's template: the outer roots are K¹, so K¹ = K_Q; the inverted
matrix is K², so K² = K_C. Hence = g_gen(K¹ = K_Q, K² = K_C) = **g(K_C ‖ K_Q)**.

**Step 8.** Huang's screening statement is about g(K_C ‖ K_Q). This project
computes it. Flórez Ablan et al. compute its reverse.

### Where this can break

Steps 1, 2, 4, 5 and 7 are each directly readable — from the two e-prints and
from two repositories. A reader can check them in an afternoon.

**Step 3 is an inference and it is the single point of failure.** If F19's bound
is not `s_{K²} ≤ g_gen² s_{K¹}`, or if Appendix F introduces g_gen for a
specific pairing without intending the general template, the whole chain
collapses and steps 6 and 8 reverse. **That step rests on one reading of
Appendix F's prose, by one person, on one occasion** — and an earlier reading of
the same appendix, from a rendering rather than source, produced a
self-contradictory transcription that supported a claim later withdrawn.

### What must change

Section 2 currently asks the reader to accept step 3. **It should quote
Appendix F's bound verbatim and let the reader perform the match**, which costs
two lines and converts the paper's sharpest claim about another group from an
assertion into a derivation. Until that quotation is in place, the claim should
be stated with its dependency named.

---

## Q2 — Section 5.6: whose failure, and what does one case show?

**The question exposes a conflation I introduced.** Section 5.6 says "the
protocol has failed its own standard, repeatedly, in public" and lists four
items. They are two different findings and should never have been merged.

| | what happened | category |
| --- | --- | --- |
| 1 | asserted from the manuscripts that two published benchmarks performed none of five checks; on reading the deposit, **six of seven claims were wrong or misleading** | **its authors asserted without checking** |
| 2 | on its first real file it required a field this project's own pipeline never emitted, collapsed fifteen configurations into one, and **silently changed three answers** | **the tool malfunctioned** |
| 3 | declared four checks unrunnable when three were not — one needed nothing at all | **its authors' judgement, unexamined** |
| 4 | the first audit against real records found four defects, **all four in the checks**, with the full suite passing on every one | **the tool malfunctioned** |

**Not one of the four is "a pipeline failed the audit criteria."** Items 1 and 3
are the protocol's authors making claims they had not verified — the same
failure the protocol exists to prevent, committed by the people who wrote it.
Items 2 and 4 are the instrument being wrong. A reader who takes 5.6 as evidence
that audited pipelines fail has read it as I wrote it and not as I meant it.

### What the single prospective case demonstrates

Week 6, against Kakavand et al.'s public Zenodo deposit via
`scripts/foreign/kakavand_adapter.py`. It produced **one measurement and eight
refusals**.

The measurement: kernel conditioning across all six deposited `ibm_fez` Gram
matrices, worst **4.5e+05**, against this project's own 7.8e+19 to 1.1e+33 —
fourteen to twenty-seven orders of magnitude better conditioned, meaning their
dual is well determined and this project's precision floor would not be needed
on their data at all.

The refusals: four required fields absent, so chance correction, power and the
precision floor each name what they cannot answer; no classical arm in the
hardware phase, so cross-arm has nothing to pair; one seed, so unit-of-analysis
warns and power cannot speak; no `inner_score`, so selection cannot be shown.

**What it demonstrates:** that the record format plus Tier 1 can produce a map
of what a stranger's deposit can and cannot support, in seconds, without their
pipeline — and that one cross-pipeline physical quantity can be compared.

**What it does not demonstrate, and 5.6 must say so:** it **found no defect in
their work and was not looking for one**. The week-6 record states this
directly: *"None of this is a criticism of their work: it is a map of what a
reader can and cannot verify from that deposit."* One run that correctly
reported its own blind spots is evidence the format is useful. It is not
evidence that these checks detect errors in other people's analyses, because on
the only occasion they met foreign data they detected none.

One further item belongs in 5.6 and is absent: on a partial sample of two of the
six Grams the conditioning check read 1.7e+04, **understating the worst case by
a factor of 26**. It was caught only because the check prints how many kernels
it sampled. That is a real limitation of Tier 2's indicative sampling and it
argues for the `--hook-sample` caveat being stronger than "indicative".

### What must change

Split 5.6's list into the two categories above. State that no item is a pipeline
failing an audit. Add what the prospective case found and, more importantly,
what it did not. Add the 26x sampling understatement.

---

## Q3 — Provenance: exactly what cannot be resolved, and what that costs

You are right that a limitation statement documents rather than repairs. Here is
the precise scope, then the repair options, because the current text offers only
the former.

### What a reader cannot resolve

Every one of the 15,120 result records carries a `git_commit` field. Three
distinct values appear — `0b796a3` (7,520 quantum), `2cf7ec7` (7,440 classical),
`0b2aef4` (160 negative-control). **None is an ancestor of `main`.** A reader
who clones the public repository can resolve none of them.

### What that specifically prevents

**A reader cannot bind any result to the code state that produced it.** They
cannot confirm that the analysis code at run time is the code now published, and
they cannot diff the two to see what differs.

Independent verification therefore degrades from *"run the code that produced
these numbers"* to *"run the current code and see whether you get these
numbers"*. **If the current code differs from the code that ran, nothing in the
repository lets a reader detect it.**

### What it does not prevent

The records themselves are intact and complete. Every analysis script is
public and readable. The data provenance is separate and unaffected —
`data/README.md` carries sources and checksums. The public half of the
tree-identity mapping is checkable: a reader can confirm that `17c92c25`,
`60d67715` and `fbbf1664` carry the stated trees. Re-running the current
pipeline on the current data and comparing is entirely open to them.

So the loss is bounded and specific: **it is the binding between a record and
its code, not the availability of either.**

### Repair, in increasing cost

1. **Annotated tags on `main`.** `git tag records-0b796a3 17c92c25`, and so for
   the other two, with the tag message carrying the tree hash and the reason.
   Cheap, in-repo, and it moves the mapping from a document a reader must find
   into an object they get by cloning. It still rests on the author's assertion
   that the mapping is correct, but the tree identity is independently
   checkable. **This is strictly better than the current prose and costs three
   commands.**
2. **Publish `prerewrite-20260925`.** Full repair: every stored hash resolves
   and the binding is verifiable without trusting anyone. The cost is the one
   D11's fourth amendment records — it restores to the public repository the AI
   co-authorship trailers the rewrite removed, undoing what the rewrite was for.
3. **Re-run and re-stamp.** Not free and not recommended. It produces new
   records, which means the published verdicts would either be recomputed from
   them or left citing records that no longer exist.

### What must change

The limitation text in the paper draft and in section 5.4 should carry the
"what it does not prevent" paragraph, because the current version overstates the
damage by not bounding it. And option 1 should be taken or explicitly declined,
since documenting a repairable problem while leaving it unrepaired is a weaker
position than either repairing it or saying why not.

---

## Summary of required changes

| document | change |
| --- | --- |
| `docs/paper-background.md` §2.2 | quote Appendix F's bound verbatim so step 3 is a derivation, not an assertion |
| `docs/paper-protocol.md` §5.6 | split tool defects from unchecked authorial claims; state that no item is a pipeline failing an audit; add what the foreign run did **not** find; add the 26x sampling understatement |
| `docs/paper-protocol.md` §5.4 | bound the provenance loss — what it does not prevent |
| `docs/paper-draft.md` §4 | same bounding in the limitations |
| repository | take or decline the tag repair |

**None of these changes a result.** All four are about the precision of claims,
which is the standard the paper sets for others.
