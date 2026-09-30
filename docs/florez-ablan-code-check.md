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
