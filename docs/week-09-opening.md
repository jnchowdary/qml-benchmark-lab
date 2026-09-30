# Week 9 opening: the g orientation is settled, and the λ rule is not sourced

**Date:** 30 September 2026.
**Prompted by:** the retraction at `292360e`, which left three items that had to be
settled before any number of Flórez Ablan et al.'s could sit beside one of this
project's.

One is settled in this project's favour on verbatim evidence. One is settled
against this project. One remains open and needs a human to read a PDF page.

---

## 1. The orientation of g is settled. This project's convention matches Huang

Two facts from Huang et al., *Power of data in quantum machine learning*, both
retrieved as **verbatim** printed text rather than summary.

**Equation (5), the unregularised definition, as printed:**

    g12 = g(K1||K2) = sqrt( || sqrt(K2) (K1)^-1 sqrt(K2) ||_inf )

followed by "where ‖·‖∞ is the spectral norm of the resulting matrix and we
assume Tr(K1) = Tr(K2) = N". The inverse is on the **first** argument. The outer
square roots carry the **second**.

**The direction, as printed:** the paper defines "consider the geometric
difference gCQ = g(KC‖KQ)", and then:

> "In contrast, if gCQ is large we show that there exists a data set with
> sC = g²CQ sQ ... with the quantum model exhibiting superior prediction
> performance."

> "If the geometric difference is small, then a classical ML method is guaranteed
> to provide similar or better performance"

corroborated independently by the Fig. 4 caption's `g(C||PQ)`.

**Therefore:** the quantity whose largeness is necessary for possible quantum
advantage is `g(K_C‖K_Q)`, and by Eq. (5) that inverts **K_C, the classical
kernel**.

This project's `geometric_difference` inverts the classical kernel. **It matches
Huang's main text.** Flórez Ablan et al.'s Eq. (6), which inverts K_2 under the
stated assignment K_1 = K_C and K_2 = K_Q, does not.

### The one part still open, and it is not a small one

Huang's **regularised** form, Eq. (F19), is in Appendix F, which could not be
retrieved as verbatim text. Two independent extractions of the truncated tail
agreed with each other on structure and returned:

    F19:  g_gen = sqrt( || sqrt(K1) sqrt(K2) (K2 + lambda*I)^-2 sqrt(K2) sqrt(K1) ||_inf )
    F20:  g_tra = lambda * sqrt( || sqrt(K1) (K2 + lambda*I)^-2 sqrt(K1) ||_inf )

As λ → 0 that tends to `sqrt(‖ sqrt(K1) K2^-1 sqrt(K1) ‖)`, which is **not** the
λ → 0 limit of printed Eq. (5). If that transcription is right, **Huang's own
appendix is index-swapped relative to Huang's own main text, and Flórez Ablan et
al. implemented F19 faithfully.** In that case their orientation is F19's, this
project's is Eq. (5)'s, and the inconsistency originates upstream in Huang rather
than with either of us.

**This is not asserted.** The retrieval that produced it was explicitly
unreliable on exactly the subscripts in question: a second, index-focused
extraction returned an internally contradictory answer for the same equation. A
claim that a widely cited Nature Communications appendix contradicts its own main
text is not made on a paraphrasing model's transcription.

**Action required, and it needs a person:** open arXiv:2011.01938v2, go to
Appendix F, subsection "Geometric difference g", and read Eq. (F19) off the page.
One line of transcription settles it. Until then this project continues to use
Eq. (5)'s orientation, which is the one it can cite verbatim, and says nothing
about F19.

---

## 2. Settled against this project: `lambda_from_svm_C` has no source

`src/qbench/kernels/geometric_difference.py:180`:

```python
def lambda_from_svm_C(C: float, n: int) -> float:
    """Map an SVM's C to the equivalent kernel-ridge regularisation lam.

    An SVM with penalty C corresponds to regularisation strength ~1/(2*C*n) in
    the kernel-ridge sense. ...
    """
    return 1.0 / (2.0 * C * n)
```

"corresponds to ... ~1/(2\*C\*n) in the kernel-ridge sense" cites nothing. It is
an asserted correspondence, hedged with a tilde, in a project whose stated rule
is that a claim must cite its source or not be made. **Nothing in what was
retrieved of Huang licenses either 1/(2C) or 1/(2Cn).** The paper prints no
SVM-to-KRR relation at all; the only λ-bearing objective surfaced, in Appendix D
and summary-derived rather than verbatim, was

    min_w [ lambda*<w,w> + SUM_i (<w,phi(x_i)> - target_i)^2 ]

with λ against an **unnormalised sum** and no 1/N anywhere in it.

### The derivation neither paper gives

Both conventions follow from the same algebra and differ only in whether the data
term is a sum or a mean. Taking scikit-learn's SVC primal:

    min_w  (1/2)||w||^2 + C * SUM_{i=1..n} xi_i

Normalising the data term to unit coefficient:

    divide by C     ->  (1/(2C))  ||w||^2 + SUM_i xi_i        so lambda = 1/(2C)
    divide by C*n   ->  (1/(2Cn)) ||w||^2 + (1/n) SUM_i xi_i  so lambda = 1/(2Cn)

So **1/(2C) is the correspondence against a summed empirical risk and 1/(2Cn) is
the correspondence against a mean empirical risk.** Neither is wrong in
isolation. What makes one of them wrong *here* is that λ in Huang's F19 belongs
to a specific objective, and the λ used to compute g must be on that objective's
scale.

The one piece of evidence about that objective, weak as it is, shows a summed
residual term, which points to **1/(2C)** and therefore to Flórez Ablan et al.'s
convention rather than this project's.

**Status: this project's λ rule may be wrong by a factor of n, and it currently
has no citation either way.** Settling it requires reading Huang's Appendix D and
F together, as printed. Same page turn as section 1.

---

## 3. What the λ convention actually costs, quantified

Measured on `results/audits/g_units.jsonl`, 7,200 rows, all 360 registered units.

Ceiling-breach rate by λ column, as the data currently stands:

| λ | rows breaching √n | share |
|---|---|---|
| 0.1 | 4 / 7200 | 0.06% |
| 0.01 | 657 / 7200 | 9.1% |
| 0.001 | 4574 / 7200 | 63.5% |
| 0.0001 | 4972 / 7200 | 69.1% |
| λ-from-C | 2893 / 7200 | 40.2% |

`lambda_from_C` currently spans 1.43e-07 to 7.14e+01, median 1.43e-03. Under
1/(2C) every value scales up by n_train, so the median moves to roughly 1.4e-01
to 7.1e-01, at or above the frozen sweep's top end.

Because g is monotone decreasing in λ, existing numbers bound the alternative
without recomputing anything: for each row, g(λ_alt) ≤ g(λ_grid) for any grid λ
not exceeding λ_alt. That gives, for the λ-from-C column under 1/(2C):

| | rows |
|---|---|
| **proven breach-free** | 5710 |
| bound inconclusive, may still breach | 1158 |
| λ_alt below the grid, cannot bound | 332 |

So at least 79% of the λ-from-C column's breaches disappear under the other
convention, and at most 21% could survive. **The frozen sweep does not cover
this**, because the alternative median sits above λ = 0.1. The λ-from-C column is
therefore convention-dependent in a way the frozen columns are not, and D5's
breach account for that column rests on an unsourced rule.

The frozen columns are unaffected. H2 and H3 as computed over the frozen sweep do
not move.

---

## 4. The λ = 0.1 column is one cell away from clean, and that cell is one cell, not four

The table above shows 4 breaching rows at λ = 0.1. They are not four independent
failures:

    churn / angle-r1 / seed 7 / n_per_class=100 / nq=4 / selectk   g=12.720  ceiling=11.832
    churn / angle-r2 / seed 7 / n_per_class=100 / nq=4 / selectk   g=12.938  ceiling=11.832
    churn / iqp-r1   / seed 7 / n_per_class=100 / nq=4 / selectk   g=12.768  ceiling=11.832
    churn / iqp-r2   / seed 7 / n_per_class=100 / nq=4 / selectk   g=12.768  ceiling=11.832

Same dataset, same seed, same training size, same feature count, same mapping,
same classical C of 1e-4, same bandwidth. **It is one (dataset, seed, size,
mapping) cell appearing under all four quantum settings, because the four
settings share one classical kernel and g's ceiling breach is driven by the
classical side.** Reported as "4 of 7200 rows" it looks like a scatter of
failures; it is one failure with multiplicity four.

The separation is stark. The four g/ceiling ratios are 1.0934, 1.0791, 1.0791 and
1.0750. The fifth-largest ratio in all 7,200 rows is **0.9150**. Nothing sits
between 0.92 and 1.07.

### This does not license dropping them, and the temptation is the point

An isolated outlier cluster, a clean gap beneath it, and a headline verdict that
would flip if it were excluded, is precisely the configuration in which a
reporting rule gets chosen from the answer. **D5 refused to pick the λ that made
g behave. D10 refused to set a breach tolerance.** Both refusals were right and
both apply here unchanged. No tolerance is introduced, no seed is excluded, no
cell is dropped, and H2's verdict does not move.

What changes is only the description. Two things must be stated wherever the
λ = 0.1 column is reported:

1. The breach count at λ = 0.1 is **one cell, with multiplicity four**, not four
   independent breaches, and the multiplicity comes from a shared classical
   kernel.
2. The excess is 7.5% to 9.3% over the ceiling, on the smallest-but-one training
   size, and the next-nearest row in the entire dataset is 8.5% *below* the
   ceiling.

A reader given "4 / 7200" and a reader given those two sentences are not equally
informed, and the second framing is the true one.

**To verify before this is relied on:** whether `units_at` already collapses this
multiplicity when it counts breaches per unit. If it counts rows, the
unit-level breach figure for λ = 0.1 is overstated by a factor of four; if it
counts cells, the figure is right and only the prose needs fixing. This has not
been checked and is the first code task of week 9.

---

## 5. Net position

| Item | Status |
|---|---|
| g orientation, this project vs Huang Eq. (5) | **Settled, matches, verbatim evidence** |
| g orientation, Flórez Ablan vs Huang Eq. (5) | **Differs**, on verbatim evidence |
| Whether Huang's F19 contradicts Huang's Eq. (5) | **Open.** Needs a person to read one PDF line |
| `lambda_from_svm_C` = 1/(2Cn) | **Unsourced.** May be wrong by a factor of n |
| Which λ convention Huang's F19 intends | **Open.** Same page turn |
| λ-from-C breach account in D5 | **Convention-dependent.** ≥79% of breaches vanish under 1/(2C) |
| Frozen λ sweep, H2, H3 | **Unaffected** |
| λ=0.1 breach count | 1 cell × 4 settings, not 4 failures. Verdict unchanged, prose must change |

No hypothesis, threshold or decision rule changes in this document. No result is
recomputed. Two of the three items that blocked a cross-reference to Flórez Ablan
et al. are now closed, and the third is a single page of a PDF.

---

# Correction to section 4, 30 September 2026

Section 4 above flagged one item as unverified: whether `units_at` counts rows or
cells, and it guessed that the unit-level breach figure at λ = 0.1 might be
"overstated by a factor of four". **The flag was right to be there and the guess
inside it was wrong.** The accounting is correct as it stands. What the check
found instead is more serious than the thing it was looking for.

---

## C1. The breach count is correct. The multiplicity claim was wrong

`UNIT_FIELDS = ("dataset", "n_per_class", "mapping", "n_qubits", "setting")`.
**`setting` is a unit field.** The four breaching rows differ in exactly that
field, so they are four *distinct units*, not one unit counted four times:

    ('churn', 100, 'selectk', 4, 'angle-r1')  ->  1 breaching seed of 20
    ('churn', 100, 'selectk', 4, 'angle-r2')  ->  1 breaching seed of 20
    ('churn', 100, 'selectk', 4, 'iqp-r1')    ->  1 breaching seed of 20
    ('churn', 100, 'selectk', 4, 'iqp-r2')    ->  1 breaching seed of 20

`units_at` counts a breach per seed-row and returns `total` as a row count, so
`breaches = 4` of `total = 7200` is exactly right and nothing is inflated.

Section 4's statement that this is "one failure with multiplicity four" is
**correct about the cause and wrong about the accounting**, and the document
should not have used the word "cell". The four units share one classical kernel,
because they share `(dataset, n_per_class, mapping, n_qubits, seed)` and differ
only in the quantum setting, and the ceiling breach is driven by the classical
side. So there is one underlying pathology. But it lands in four units, and the
unit table is entitled to count it four times.

Also established, by replicating `units_at` against the registered data:

| λ | units in table | excluded | breaching seeds | of | breach-free? |
|---|---|---|---|---|---|
| 0.1 | **360** | **0** | 4 | 7200 | no |
| 0.01 | 350 | 10 | 657 | 7200 | no |
| 0.001 | 90 | 270 | 4574 | 7200 | no |
| 0.0001 | 61 | 299 | 4972 | 7200 | no |
| from_C | 289 | 71 | 2893 | 7200 | no |

Each of the four affected units retains 19 of 20 seeds against `MIN_SEEDS = 10`,
so **no unit is excluded at λ = 0.1.** The unit table at that column is complete
at 360 of 360.

---

## C2. The finding this check actually produced

`scripts/geometric_tests.py`, line 662:

```python
# D5: the conclusion must hold at every lambda with no ceiling breach.
clean = [c for c in LAM_COLS if report["by_lambda"][c]["breaches"] == 0]
...
if not clean:
    out = "NOT ESTABLISHED (no breach-free lambda)"
```

The gate is `breaches == 0`. **One breaching seed anywhere in a λ column
disqualifies that entire column**, regardless of how many units survive or how
complete the table is.

At λ = 0.1 the column is otherwise pristine: all 360 units present, none
excluded, and the largest g/ceiling ratio among the remaining 7,196 rows is
**0.9150**. Four seed-rows breach, at ratios 1.0934, 1.0791, 1.0791 and 1.0750.
Nothing in the data sits between 0.92 and 1.07.

Those four rows are 0.056% of the registered observations.

**Therefore: both H2's and H3's NOT ESTABLISHED verdicts rest entirely on four
seed-rows out of 7,200.** `clean` is empty only because λ = 0.1 fails by four
rows; every other column fails by hundreds or thousands. Had those four not
breached, `clean` would be `['0.1']` and the script would report a substantive
verdict at a column with a complete 360-unit table.

This was not stated anywhere in the week-7 record, in D10, or in section 4 above.
It is the most important structural fact about the project's headline result and
it went unremarked for five days.

---

## C3. What must not happen now, stated before the temptation arrives

An isolated four-row outlier cluster, a clean gap of 0.15 beneath it, a single
shared classical kernel as the cause, and two headline verdicts that would become
substantive if those rows were excluded. That is the most favourable-looking
exclusion case this project will ever be offered.

**No tolerance is introduced. No seed is excluded. No unit is dropped. The rule
at line 663 stands exactly as pre-registered, and H2 and H3 remain NOT
ESTABLISHED.**

D5 refused to choose the λ that made g behave. D10 refused to set a breach
tolerance. Both refusals were made before this dependency was visible, and they
are worth more now than when they were made, because a rule that only binds when
it costs nothing is not a rule. The strict gate is currently doing precisely the
job it was written for: declining to certify a result from a column with a known
and undiagnosed pathology in it.

What changes is disclosure, not the verdict. Three things must appear wherever H2
or H3 is reported:

1. The NOT ESTABLISHED verdict is produced by `clean` being empty, and λ = 0.1
   fails that test by **four seed-rows of 7,200**, with all 360 units present.
2. The four rows share one classical kernel configuration: churn, seed 7,
   n_per_class = 100, n_qubits = 4, selectk. The cause is one, the accounting is
   four.
3. The next-largest g/ceiling ratio in the entire dataset is 0.9150, so the
   verdict is not marginal in the usual sense of sitting near a threshold. It is
   **discontinuously** dependent on four observations.

A reader told "NOT ESTABLISHED at every λ" and a reader told those three
sentences hold different beliefs about how much this project has established. The
second reader is correctly informed.

---

## C4. The diagnostic question that is legitimate

Asking *why* that one classical kernel breaches at λ = 0.1 is science, not
rule-shopping, and it is the right next task. The configuration is the
second-smallest training size (n_train = 140, ceiling = 11.832) at the smallest
feature count (n_qubits = 4) under `selectk`, with the classical arm's selected
`C = 1e-4`, the bottom of the grid.

A kernel built from four `selectk` features on 140 training points is the most
rank-deficient classical kernel in the study, and D5's own result is that the
classical factor of g is capped at 1/(4λ), so a breach at λ = 0.1 requires
‖K_Q‖/n > 0.4. Whether that cell's K_C is degenerate enough to explain a 7.5% to
9.3% excess is checkable directly from the kernel matrices, and checking it is
what would turn "four rows breach" into an explanation.

**This is recorded as the question, not the answer.** Three mechanisms for a
ceiling breach have already been proposed in this project and refuted this month,
the third of them one message from the permanent record. No mechanism is asserted
here.

---

## C5. Net change

| Item | Status |
|---|---|
| `units_at` counts rows, not cells | **Verified.** `breaches = 4 / 7200` is correct |
| Section 4's "overstated by a factor of four" | **Withdrawn.** The count was never inflated |
| Section 4's "one cell, multiplicity four" | **Corrected.** Four distinct units, one shared cause |
| Units excluded at λ = 0.1 | **Zero.** Table complete at 360 of 360 |
| H2 and H3 NOT ESTABLISHED depends on | **Four seed-rows of 7,200**, newly stated |
| The breach rule at line 663 | **Unchanged**, and not to be changed |
| H2, H3 verdicts | **Unchanged** |

No threshold moves, no rule is relaxed, and no number is recomputed. One wrong
claim of mine is withdrawn, and one fact about the fragility of the project's
headline result is placed on the record for the first time.
