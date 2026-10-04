# Section 7 — Deviations

This section is a pointer, not a summary. Summarising a deviations record
reintroduces exactly the discretion the record exists to remove, so the
authoritative documents are named here and the reader is sent to them.

---

## 7.1 The two documents, and the rule between them

**`docs/pre-registration.md` v1.0 is the registered design and is never
edited.** Where it is wrong, it stays wrong and the correction lives elsewhere.
Three of its statements are known to be false as written — a claim of OSF
registration, a claim that two cited commit hashes are on `main` and public, and
the whole of its statistical power table — and all three remain in the document
with their corrections recorded against them. This is deliberate: a registration
that is edited after results are seen is not a registration.

**`docs/deviations.md` is authoritative for every change.** Fifteen records, D1
to D15, several carrying dated amendments. Each states what moved, when it was
decided, when it was declared, and whether the affected results had been seen.

**Where the two disagree, the deviations record governs**, and the
pre-registration's text is the historical object rather than the operative one.

---

## 7.2 Where to start

| if you want to know | read |
| --- | --- |
| what was registered, before anything moved | `docs/pre-registration.md` v1.0 |
| every movement from that design, in one table | **§3.9 of this paper** |
| why a given movement was made, and when it was declared | the numbered record in `docs/deviations.md` |
| what is still undecided | D14, below |

**§3.9 is the index.** It lists all nine movements with their direction — which
added a constraint, which weakened a claim, which removed planned evidence — and
is the fastest route to whether any of them could have manufactured a result.
None did: D2, D5, D7 and D8 make the tests harder to pass; D6 and D13 weaken
what may be claimed; D12 removes evidence never collected; D15 is editorial.

---

## 7.3 One record is open

**D14 is a draft and is not in force.** It establishes that this project's
λ-from-C helper returns 1/(2·C·n) on an uncited assertion, that Huang prints no
such correspondence, and that his Appendix D objective points to 1/(2C)
instead. No option among its three candidates has been adopted, no g has been
recomputed, and no verdict has moved.

**What rests on it:** one supplementary λ column. **What does not:** the frozen
λ sweep at {1e-1, 1e-2, 1e-3, 1e-4} that carries every result reported here.

D14 also records why it remains a draft. Two of its three candidate resolutions
could convert a NOT ESTABLISHED verdict into a substantive one, and it was
written after that verdict was known. Its own requirement is that the chosen
option and the mapping from each outcome to each verdict be committed and pushed
*before* any recomputed value is examined.

---

## 7.4 Two records a sceptical reader should go to first

**D13**, because H3 was ungated from H2 in week 4 for a stated reason, the
departure was recorded in a weekly narrative rather than in `deviations.md`, and
it was not declared until after H3's result had been computed and published.
D13 offers two readings and does not choose between them. **D15 is the second
instance of the same failure**, for the paper's framing, declared nine days
late.

**D11 and its four amendments**, because they govern how much this project's
own ordering evidence is worth. There is no external registration and no
pre-result external timestamp; the history was rewritten on 25 September 2026;
and every result record stores a commit absent from the public repository. The
tags `records-0b796a3`, `records-2cf7ec7` and `records-0b2aef4` map those
identifiers to public counterparts and state in their own messages which half of
that correspondence a reader can check.

**Every ordering claim in this paper — including the claims in D13 and D15 that
a decision preceded a result — rests on evidence of that class.** A reader who
does not accept an author-controlled history as evidence of ordering should
discount those claims accordingly, and the records say so rather than leaving it
to be noticed.
