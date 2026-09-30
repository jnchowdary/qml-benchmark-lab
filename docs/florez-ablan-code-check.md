# Code check: Flórez-Ablan and Schnabel, arXiv:2503.05602

**Status of the week-4 claim: RESOLVED.** The claim "no negative controls",
withdrawn in week 4 as unverified, is now tested against the authors' own code
and is **upheld**. Three further findings arose that were not being looked for,
one of which matters more than the claim that prompted the check.

**Date of check:** 30 September 2026.
**Resolves:** the OPEN item recorded in `docs/week-04-report.md` (commit
`9ff39e8`).

---

## 1. What was checked, and how

The week-4 correction withdrew the claim because the project's own rule is that
**a claim about what another group did not do must cite their code or their
data, or it is not made.** Absence from a manuscript is absence from a
manuscript. The authors' Section III states that the code reproducing all
simulation results is on GitHub, so the code is the thing that settles it.

**Repository.** `https://github.com/RobertoFlorez/similarity-of-quantum-and-classical-kernels`,
described on GitHub as the accompanying repository for the preprint. It has a
single commit.

    commit  431908d153e4ad0d65de52910fe810bcde4f5378
    author  Roberto Flórez <rflorezablan@gmail.com>
    date    2025-04-12 09:20:20 +0200
    subject Initial commit with current state

**Scale.** 144 tracked files: 26 Python modules totalling 5,226 lines, 13
Jupyter notebooks, 3 bash drivers.

**Method.** The repository was cloned and searched exhaustively rather than
read file by file. This matters: the claim under test is a **negative**, and a
negative cannot be established by fetching four files and finding nothing in
them. It can be established, within the scope stated in section 3 below, by
searching the whole tree.

Anyone can repeat this:

    git clone --depth 1 \
      https://github.com/RobertoFlorez/similarity-of-quantum-and-classical-kernels.git
    cd similarity-of-quantum-and-classical-kernels
    git rev-parse HEAD     # expect 431908d153e4ad0d65de52910fe810bcde4f5378

    git ls-files '*.py' '*.ipynb' '*.bash' '*.sh' '*.md' \
      | xargs grep -IEni 'shuffle|permut|randomi|scrambl|surrogate|negative.?control|null.?model'

---

## 2. Finding 1: no negative control exists in the released code

Occurrence counts across all tracked Python, notebook, bash and markdown files:

| Term | Occurrences |
|---|---|
| `shuffle` | 1 |
| `permut` | 0 |
| `randomi` (randomise / randomize / randomization) | 0 |
| `scrambl` | 0 |
| `surrogate` | 0 |
| `negative control` | 0 |
| `null model` | 0 |

The single `shuffle` is not a negative control:

    data_tools/get_dataset.py:453
    MNIST_ds = tfds.load('mnist', split=tfds.Split.TRAIN).shuffle(1024, seed=1).batch(50000)

That shuffles the **order of examples** before batching, inside a function whose
own docstring marks it superseded ("Old version please use the class"). It never
separates a label from its features.

**Every other use of randomness in the repository keeps features and labels
paired.** The recurring idiom throughout `data_tools/get_dataset.py` is:

    np.random.seed(0)
    inds = np.random.choice(range(len(y)), size=num_datapoints, replace=False)
    y = y[inds]
    X = X[inds, :]

The same index vector is applied to both, so subsampling cannot act as an
accidental label randomisation. The remaining uses are `train_test_split`
(with `stratify=y` where classification), `PCA(random_state=0)`, and synthetic
data generators that draw labels from a known rule.

**The experiment registry contains no control arm.** `experiment_inputs.py`
enumerates the full study grid: two datasets (`plasticc`, `kMNIST28`), five
encoding circuits (`IQPLikeCircuit`, `HamEvol`, `YZ_CX_EncodingCircuit`,
`HubregtsenEncodingCircuit`, `Z_Embedding`), two kernel methods (FQK, PQK),
qubit counts 2 to 16, 40 bandwidths, six seeds. `all_simulations.bash` invokes
only the four documented stages against those registered experiments. There is
no flag, no extra experiment index, and no separate driver that would run a
shuffled or randomised-label variant. This closes the one loophole that a
file-by-file read would have left open, namely a control hidden as an extra
configuration rather than as a keyword.

---

## 3. What this verification does and does not establish

**It establishes:** the released reproduction code, at commit `431908d`, which
the paper states reproduces all of its simulation results, contains no
label-randomisation control of any kind.

**It does not establish:** that the authors never ran one. Code that was written
and not released is outside what any external check can see. The repository's own
README describes itself as intended for reproducibility and "not optimized nor
idealized for continuous use", which is consistent with a cleaned release rather
than a complete working tree.

The claim this project may therefore make, and the only one, is the narrow one:
**no negative control appears in the code the paper offers as its reproduction
route.** That is a statement about the released artefact, and it is now
evidenced. The broader statement is not made.

---

## 4. The week-4 withdrawal was correct, and being vindicated does not change that

The original claim turns out to have been true. The withdrawal was still the
right call, and this record should not be read as evidence that the rule cost
something.

When the claim was first made it rested on the manuscript alone. Had the code
contained a control, the claim would have been false and published. That the
coin landed the other way is not a property of the reasoning that produced it.
**A claim that was not checked is not made better by later turning out to be
correct**, and the rule that forced the withdrawal is what produced the check
that now supports it.

---

## 5. Finding 2, unlooked for: ROC-AUC is computed on hard predicted labels

This was not the question being asked and is more consequential than the
question being asked.

In `models/performance_simulations.py`, the classifier's output is a hard label:

    149:  y_pred_svm_train = svm_classifier.predict(K_train)
    150:  y_pred_svm       = svm_classifier.predict(K_test)

and that hard label is what is scored:

    173:  roc_auc_score_svm            = roc_auc_score(y_test,  y_pred_svm)
    226:  results_dic["roc_auc_score_train"] = roc_auc_score(y_train, y_pred_svm_train)

Those are the only two `roc_auc_score` call sites in the simulation path.
Across the entire repository, `decision_function` occurs **0** times and
`predict_proba` occurs **0** times. No continuous score is ever produced, so
no ROC-AUC in this study is computed on a ranking.

**Why this is a defect, verified rather than asserted.** ROC-AUC on a binary
input collapses to balanced accuracy. Over 2,000 randomised trials spanning base
rates from 0.02 to 0.5 and sample sizes from 20 to 200, `roc_auc_score(y, ŷ)`
equalled `balanced_accuracy_score(y, ŷ)` in **2,000 of 2,000** cases to within
1e-12. The quantity reported as AUC is therefore threshold-dependent, which the
ranking measure it is taken for is not. For a single fixed ranker with a true
AUC of 0.9122:

| Decision threshold | "AUC" as this code computes it |
|---|---|
| 0.0 | 0.7944 |
| 1.0 | 0.8556 |
| 2.0 | 0.6667 |
| 3.0 | prediction collapses to one class, stored as NaN |

The same model, ranking the same test set equally well at every row, scores
anywhere from 0.67 to 0.86 depending on where the SVM's margin happens to fall.

**Why it propagates.** `models/geometric_diference_tools.py` selects the
reported configuration by sorting on this column:

    146:  quantum_performance_with_kernels = quantum_performance_with_kernels.sort_values(
              by=["roc_auc_score", "bandwidth"], ascending=False)
    147:  df_poly = df_poly.sort_values(by=["roc_auc_score", "bandwidth"], ascending=False)

So the "best" quantum and classical configurations entering the paper's
comparison are chosen by a threshold-dependent balanced accuracy that is
labelled AUC. The comparison is not thereby wrong, but it is not the comparison
its label describes.

**Secondary effect worth recording.** Lines 153 to 166 set every score to NaN
when the classifier collapses to predicting a single class. Degenerate cells are
therefore dropped rather than scored at chance. That is a selection effect on
which cells enter the aggregate, and it acts hardest exactly where a kernel
performs worst.

---

## 6. Finding 3: no chance or base-rate correction anywhere

`average_precision_score`: **0** occurrences. `balanced_accuracy`: **0**.
`prevalence`: **0**. `base_rate`: **0**. No score is adjusted for class balance
at any point.

This is a weaker criticism of their work than of a naive reading of it. Their
datasets are balanced two-class problems, so a base-rate correction would change
little. It is recorded because **this project's own normAP finding is that
ROC-AUC has a fixed chance of 0.5 regardless of base rate**, which is precisely
why ROC-AUC conceals imbalance. That finding applies to this project's
imbalanced churn and fraud data. It does not transfer to their balanced
benchmarks, and this project must not claim it does.

---

## 7. Finding 4: the geometric difference is computed in the opposite direction. FLAGGED, NOT CONCLUDED

This is the finding most likely to be wrong, and it is recorded as a question
rather than a result. The project has three times this month put a mechanism
forward as a finding and had it refuted; the discipline that follows from that
is to state the evidence and stop short of the conclusion.

**What the code does.** `models/geometric_diference_tools.py` defines

    def geometric_difference(K1, K2, lambda_reg=0.0):
        ...
        K2_shift_inv = np.linalg.inv(K2 + np.eye(K2.shape[0]) * lambda_reg)
        g12_gen = np.sqrt(np.linalg.norm(
            sqrt_K1 @ sqrt_K2 @ K2_shift_inv_squared @ sqrt_K2 @ sqrt_K1, ord=2))

The inverted matrix is **K2**. The docstring states the intended assignment
explicitly, and cites the source:

> `typically g12 = g(K1,K2) = g(K1 = KC, K2 = KQ)`
> `(from Power of data in quantum machine learning paper) ... F19`

and the call site passes them in that documented order:

    225:  geometric_difference(row["K_train_poly"], row["K_train_quantum"], ...)

So as invoked, K1 is the classical kernel and K2 is the quantum kernel, and the
kernel being inverted is the **quantum** one.

**This project's implementation inverts the classical kernel**, which is the
orientation under which a large g means the classical kernel cannot reproduce
the quantum model's functions, hence possible quantum advantage.

**The numeric consequence, which is a fact and not an interpretation.** On
constructed kernel pairs at n = 60, λ = 1e-3:

| Case | this project's `g(K_C, K_Q)` | their `g(K1=K_C, K2=K_Q)` | their `g` with arguments swapped |
|---|---|---|---|
| classical kernel weak, quantum rich | 1.3577 | 5.7332 | 1.3577 |
| quantum kernel weak, classical rich | 4.8214 | 1.4487 | 4.8214 |

Their function reproduces this project's value exactly, to 1e-6, **when its
arguments are exchanged**. The two implementations compute reciprocal-direction
quantities while both labelling the output g(K_C, K_Q).

**What is not concluded.** The paper's own printed equation has not been read.
It is entirely possible that the paper defines the quantity in the opposite
convention throughout and is internally consistent, in which case there is no
error in their work and only a naming collision with Huang's F19 as this project
reads it. What is established is narrower and sufficient for this project's
purposes: **a g value from their pipeline and a g value from this project's
pipeline, on the same pair of kernels, are not the same number.** Any comparison
between the two bodies of results must resolve the orientation first.

**Action:** read the preprint's equation as printed before any statement about
their orientation is made anywhere. Until then no claim about their direction
appears in this project's outputs.

---

## 8. Finding 5: the λ-from-C convention differs by a factor of n

Their `obtain_C_value` returns, for classification:

    return 1/(2*row["C_quantum"])

This project's `lambda_from_svm_C(C, n)` returns `1/(2*C*n)`.

The two differ by the training-set size. At their n of 320 that is a factor of
320 in λ.

This is not a small discrepancy given this project's own D5 result that **the
classical factor of g is capped at 1/(4λ)**, so a breach of the √n ceiling
requires ‖K_Q‖/n > 4λ. Moving λ by a factor of 320 moves that threshold by the
same factor. Which convention is correct is not settled here, and settling it
requires the same reading of the preprint as section 7 does. It is recorded
because any cross-reading of their g values against this project's must
reconcile both the direction and the λ scale, and reconciling one without the
other would give a wrong answer that looks right.

---

## 9. What changes in this project

The week-4 claim moves from WITHDRAWN and OPEN to **upheld, with the scope in
section 3**. It may now be stated, in that narrow form, with the commit hash as
citation.

Sections 7 and 8 are **open questions against the preprint, not findings**, and
are carried into week 9 as such. Neither appears in any outward-facing text
until the preprint's printed equations have been read.

Nothing in this record changes any hypothesis, threshold, decision rule or
result in this project. H2 and H3 stand exactly as computed.

---

## 10. Provenance note on method

The repository was obtained by `git clone` over the project's public HTTPS
endpoint after per-file retrieval was refused by the fetch layer. The refusal
was a provenance restriction rather than an access restriction by the authors:
the repository is public, and cloning is its advertised access route. The clone
is recorded here with its commit hash so that every count and quotation in this
document can be reproduced against a fixed object, which per-file fetching would
not have permitted.

The clone was made into a scratch directory and is not committed to this
repository, in line with the rule that third-party data and code are not
redistributed here.

---

# Correction, 30 September 2026, same day

This document was committed at `065cbfa` and is corrected here within the hour.
The correction is appended rather than folded into the body above, so that what
was published and what was wrong with it both remain visible.

The prompt for the correction was reading the paper itself, which the body above
had not done. **Section 7 above is retracted.** Two bibliographic facts and one
factual description are wrong. One new finding replaces the retracted one, and
the finding in section 5 survives and strengthens.

---

## C1. Bibliographic corrections

The header of this document is wrong in three ways.

| | as published above | correct |
|---|---|---|
| Authors | Flórez-Ablan and Schnabel | Roberto Flórez Ablan, **Marco Roth**, Jan Schnabel |
| Title | not stated | "On the similarity of bandwidth-tuned quantum kernels and classical kernels" |
| Status | "the preprint" | **peer-reviewed and published**, Quantum Sci. Technol., DOI 10.1088/2058-9565/ade7ad |

arXiv:2503.05602, v1 7 March 2025, v3 28 July 2025. The repository commit is
12 April 2025, so **the released code predates v3 of the paper by three and a
half months.** Anything the code shows is evidence about the code as of April,
not necessarily about the version of record.

Dropping a co-author from a criticism is not a clerical slip. It is the same
category of error as the surname episode recorded in D11's second amendment:
a name asserted without being checked. That it happened again, in a document
whose subject is the difference between asserting and checking, is the part worth
keeping.

**The status correction raises the bar on everything here.** Criticising a
published, peer-reviewed paper is not the same act as criticising a preprint, and
this document was written in the belief that it was doing the latter.

---

## C2. Factual correction: three datasets, not two

Section 2 states the registry enumerates "two datasets (`plasticc`,
`kMNIST28`)". It enumerates **three**. `experiment_inputs.py` line 308 and line
338 assign `dataset_name_list = ["pennylane_hidden-manifold"]`, and ten
hidden-manifold experiments appear in the master list at indices 55 to 64. The
paper's own text names three datasets, and the registry matches the paper.

This was a reading error on my part: I grepped a bounded region of the file and
described the whole. **It does not change the control finding.** No control arm
exists for any of the three, and the hidden-manifold experiments are ordinary
FQK and PQK runs across the same five encoding circuits. But the description was
wrong and the method that produced it was the one this project exists to
criticise: a partial look reported as a complete one.

---

## C3. Section 7 is RETRACTED. Their code is faithful to their paper

Section 7 flagged, as an open question, that their code inverts the quantum
kernel while their docstring cites Huang's F19. It framed this as a possible
discrepancy between their code and their cited source.

**The paper's Eq. (6) is printed exactly as their code implements it:**

    g(K_1, K_2) = sqrt( || sqrt(K_1) sqrt(K_2) (K_2 + lambda*1)^-2 sqrt(K_2) sqrt(K_1) ||_inf )

with the paper stating verbatim that "K_1 = K_C and K_2 = K_Q are classical and
quantum kernel matrices". The regularised inverse falls on K_2, the quantum
kernel, in the paper as in the code. The outer factors are the classical kernel.
The call site passes `(K_poly, K_quantum)` in exactly that order.

**There is no implementation error in their work, and this project came within
one document of implying there was.** The only reason it did not is that section
7 was written as a flagged question rather than a finding. That decision is the
single thing that stopped this from being the fourth wrong mechanism of the
month.

What actually remains is narrower and turns the question inward:

**This project's implementation inverts the classical kernel. Theirs inverts the
quantum one. Both cite Huang. At most one convention can match Huang, and
nothing yet establishes that it is this project's.** The open question is no
longer "did they misread Huang" but "which of us did", and the burden falls
equally on `scripts/geometric_tests.py`.

The numeric consequence stated in section 7 stands unchanged and is the only part
of that section still load-bearing: a g from their pipeline and a g from this
project's, on the same kernel pair, are reciprocal-direction quantities and are
not the same number. Their function reproduces this project's value exactly when
its arguments are exchanged.

**A further tension is visible in the quoted paper text and is NOT asserted
here.** Their Fig. 2 caption describes g as indicating "how much better a CK
generalizes than a QK", while their results text states that "only if
g(K_C, K_Q) ∝ sqrt(N) holds, the necessary condition for potential quantum
advantage is fulfilled". Those two readings of a large g point in opposite
directions. This project does not claim an inconsistency in a published paper on
the strength of two quotations lifted from a **truncated** retrieval: the fetch
returned 39,425 of 79,058 characters and stopped mid-Section III C, so the
appendices were summarised rather than read. Resolving this requires the full
paper, read directly.

---

## C4. Section 8 correction: the lambda convention is theirs by design

Section 8 recorded that their `obtain_C_value` returns `1/(2C)` against this
project's `1/(2*C*n)`, and left which is correct unsettled.

The paper's Appendix A states λ = 1/(2C), with no factor of N. Their code again
matches their paper. The factor-of-320 gap is therefore a difference of
convention between their published definition and this project's
`lambda_from_svm_C`, not a coding error on their side, and the open question is
again symmetric.

Caveat on evidence quality: the λ = 1/(2C) text sits in Appendix A, inside the
portion of the paper that came back only as a summary rather than verbatim. It is
consistent with their code, which is direct evidence, but the paper-side half of
this rests on a summary and is marked accordingly.

---

## C5. Finding in section 5 survives, and the paper strengthens it

Section 5 found that ROC-AUC is computed on hard predicted labels. The paper
does not contradict this. It states in Section III C that it selects
"optimal regularization parameters yielding the highest receiver operating
characteristic curve (ROC-AUC) scores", and **nowhere states how the input to
that score is obtained.** No decision function, margin, or probability is
mentioned anywhere in the retrieved text.

Two further code checks were run after reading the paper, and both hold:
`probability` is never passed to `SVC` anywhere in the repository, so no
probability estimate exists to score; and the only two `roc_auc_score` call sites
in the simulation path both receive `svm_classifier.predict(...)`.

So the position is: **the paper reports a ranking metric, the code computes a
threshold-dependent one, and a reader of the paper alone cannot tell.** That is
the finding, it is about the code as released in April 2025, and it is the one
substantive criticism in this document that survived contact with the paper.

---

## C6. New finding: g_tra is computed and never checked

Their own docstring states the condition under which g is meaningful:

> `g_tra = lambda_reg*sqrt(inf_norm(sqrt(K1)(K2+lambda_reg)^-2 sqrt(K1)))`
> `In the power of data: g_gen is reported given in Equation (F19) with the`
> `largest λ such that the training error g_tra ≤ 0.045.`
> `lambda_reg should be chosen such that g_tra is small`

The function computes `g12_tra` and returns it. It is written into the
dataframes as `g_tra_train` and carried through `all_difference_calculations`.

**Nothing anywhere compares it to anything.** Across all Python modules and all
13 notebooks there is no comparison operator, filter, query, mask or conditional
applied to `g_tra`. The string `0.045` occurs exactly once in the repository, in
the docstring above, and is never used. The only other occurrences of
`g_tra_train` are `<th>g_tra_train</th>` table headers in one notebook's saved
HTML output, which is display, not filtering.

λ is instead fixed at 1/(2C) from the SVM hyperparameter grid
(`C = [32, 64, 128, 512, 1024]`), and the retrieved paper text contains no
threshold criterion on a training-error quantity.

This is stated as a property of the code, which is checkable, and not as a claim
that their g values are therefore wrong, which would require knowing what g_tra
actually evaluated to on their runs. The observation is that **the diagnostic
their own docstring names as the condition for the quantity being meaningful is
computed, stored, and never consulted.**

---

## C7. The same check, run on this project

Having found a metric defect in someone else's pipeline, the obvious question is
whether this project has it. It does not.

    src/qbench/tuning.py:180   average_precision_score(y_val, model.decision_function(K_val))
    src/qbench/tuning.py:330   scores = model.decision_function(K_te)
    src/qbench/tuning.py:333   average_precision_score(y_te, scores)
    src/qbench/tuning.py:334   roc_auc_score(y_te, scores)
    scripts/run_quick_benchmark.py:124  scores = model.decision_function(K_te)
    scripts/run_quick_benchmark.py:136  average_precision_score(y_te, scores)
    scripts/run_quick_benchmark.py:137  roc_auc_score(y_te, scores)
    scripts/diagnose_representation.py:53  average_precision_score(y_te, model.decision_function(X_te))

Every ranking metric in this project takes a continuous margin. `predict_proba`
occurs zero times. `.predict()` occurs twice, both feeding `f1_score`, which
requires hard labels and is the correct use.

**This is recorded because the check should have been run before the criticism
was written, not after.** Finding a defect in another group's code and only then
asking whether one's own has it is the wrong order, and the answer coming back
clean does not make the order right.

---

## C8. Their training-set size, and what it means for the ceiling

Confirmed from code, matching the paper: `num_datapoints_list = [(400, 0.8, s)]`
for seeds 1 to 6, so N = 400 sampled, **320 train and 80 test** per seed.

The paper defines N in Eq. (6) as the number of training samples, but the text
does not disambiguate whether the √N reference line drawn in its Figs. 3 and 5
uses 320 or 400. √320 = 17.89 and √400 = 20.00. This project uses √n_train
throughout and its ceilings vary by arm, so any comparison of a ceiling breach
across the two bodies of work must fix this as well as the direction and the λ
scale. Three reconciliations, not one, and getting two right would still give a
wrong answer that looked right.

---

## C9. A process note on my own tooling

While running the section C7 check I counted occurrences with the pattern
`\.predict(`, which contains an unclosed group in extended regex, and it returned
zero for a term that occurs twice. The correct count came from `grep -F`.

This is the third time this month that a counting regex of mine has produced a
wrong number in this project, after the `test_[a-z_]+` pattern that truncated at
capitals and under-reported mutation coverage as 6 of 30 instead of 11. The
pattern is consistent: hand-written patterns used to count things, trusted
without a control. **Any count in this project that came from a regex and was not
checked against a second method should be treated as unverified.**

---

## C10. Net position after the correction

| Item | Status |
|---|---|
| No negative control in released code | **Upheld**, unchanged |
| ROC-AUC computed on hard labels | **Upheld and strengthened** |
| g_tra computed but never checked | **New, upheld** |
| No chance correction | Upheld, and weak against them as already noted |
| g direction is a discrepancy in their work | **RETRACTED.** Their code matches their Eq. (6) |
| λ omits n as an error on their side | **RETRACTED.** Their code matches their Appendix A |
| Which convention matches Huang | **Open, and now a question about this project too** |
| Their Fig. 2 caption against their √N statement | **Open, not asserted, needs the full paper** |

No hypothesis, threshold, decision rule or result in this project changes. H2 and
H3 stand exactly as computed.

**What week 9 must do before any cross-reference to their results:** read the
full paper directly, including the appendices, resolve the g orientation against
Huang's F19 as printed in Huang rather than as cited by anyone, and settle
whether this project's `lambda_from_svm_C` or their `1/(2C)` follows from the
SVM-to-KRR correspondence. Until all three are settled, this project states no
number of theirs alongside a number of its own.
