# QML Benchmark Lab — Week 1 Record

Written 17 September 2026. A plain record of what was built, what was found, and what was decided.

---

## 1. What this project is

The short version: we are testing whether a number you can calculate **before training anything** tells you in advance whether a quantum kernel SVM has any chance of beating a normal classical one on ordinary business data.

That number is the **geometric difference**, written g(K_C ‖ K_Q), from a 2021 paper by Huang and colleagues at Google. It compares two kernel matrices — one from a classical method, one from a quantum circuit — and asks how differently they see the same data.

- If g is close to 1, the classical kernel can reproduce whatever the quantum one does. Quantum advantage is **ruled out**.
- If g is close to √n, there exists some way of labelling the data where the quantum kernel sees structure the classical one cannot. Advantage is **not ruled out**, which is not the same as saying there is one.

### Why this and not a straight quantum-versus-classical comparison

Because that comparison has already been run, and recently. In April 2026, Kakavand, Strohmeyer and Schlotter at SHARE at FAU (a joint Schaeffler and Friedrich-Alexander-Universität lab) published arXiv:2604.18837. They tested four quantum feature maps, both fixed and trained, against three classical kernels across nine UCI and OpenML datasets, with real hardware validation on IBM's 156-qubit `ibm_fez`.

Their result: **none of 29 quantum-versus-classical comparisons reached statistical significance.** The single competitive quantum result cost roughly 2,000 times the classical compute.

Two things they did not do, and those two gaps are this project:

1. They did not use the geometric difference as a pre-screen. They used kernel-target alignment and their own spectral analysis instead.
2. They used biomedical and physical-science datasets. No fraud, no churn, no business data.

So the honest framing is this. We expect to find no quantum advantage, because that is what the literature keeps finding. The contribution is not a surprise win. It is answering whether the pre-screening metric actually predicts the outcome, on a class of data nobody has checked.

---

## 2. What exists now

Repository: `github.com/jnchowdary/qml-benchmark-lab`, private, Apache-2.0.
Local copy: `~/Documents/qml-benchmark-lab`.
Two commits on `main`. CI green.

### The files and what each one does

| File | What it does |
| --- | --- |
| `src/qbench/kernels/geometric_difference.py` | The metric itself. The single most important file in the repo, and the one most likely to be scrutinised by a reviewer. |
| `src/qbench/kernels/qiskit_kernels.py` | Builds quantum kernels using Qiskit's ZZ and Z feature maps. Includes a cost estimator so a bad configuration can be refused before it wastes an afternoon. |
| `src/qbench/kernels/pennylane_kernels.py` | The same idea in PennyLane, with angle and IQP embeddings. Deliberately exposes the same interface so nothing downstream has to know which framework produced a kernel. |
| `src/qbench/kernels/classical.py` | Linear, RBF and polynomial kernels, plus the logic that picks which classical kernel the quantum one gets measured against. |
| `src/qbench/features.py` | Squeezes a dataset's features down to a handful of qubits (three ways: PCA, random projections, or picking the most informative columns), then scales them into rotation angles. |
| `src/qbench/data.py` | Loads datasets, makes reproducible train/test splits, and cuts the data down to a size a quantum kernel can actually handle. |
| `tests/` | 75 tests. 42 of them exist purely to pin down the behaviour of the geometric difference metric. |
| `scripts/run_quick_benchmark.py` | A three-minute demo of the whole pipeline. Enforces its own time limit so the "under 30 minutes" claim is tested, not just claimed. |
| `configs/quick.yaml` | The demo settings. Deliberately separate from the real experiment settings so nobody confuses one for the other. |
| `requirements.txt`, `requirements.lock.txt` | Exact versions. Every single one pinned. |
| `.github/workflows/ci.yml` | Runs the tests and the demo on every push, on a clean machine. |

---

## 3. What we found that changed the plan

This is the part worth reading twice. Week 1 was supposed to be a formality. It broke five things.

### 3.1 The metric was wrong, and worse, it was unstable

The first draft of the geometric difference calculation was mathematically incorrect. Fixing the maths exposed a bigger problem underneath.

Measured on random kernel pairs of size 12, where the theoretical ceiling is √12 = 3.46:

| How ill-conditioned the classical kernel was | g at low regularisation |
| --- | --- |
| 3.2 × 10² | 9.1 |
| 3.6 × 10² | 10.4 |
| 1.5 × 10³ | 25.1 |
| 6.8 × 10³ | 58.8 |
| 2.1 × 10⁴ | 72.1 |

Read that column on the right. It is not measuring quantum separation. It is measuring how numerically awkward the classical kernel is. The correlation with conditioning is almost perfect.

**What this would have cost.** The headline figure of the paper is a scatter plot of g against actual performance. Built on this calculation, that plot would have been noise, and nothing about it would have looked wrong. It would have survived to week 9 and possibly into a submission.

**The rules that now come out of this**, enforced in the code:

1. Always use the regularised version, with the regularisation strength stated explicitly.
2. Set that strength from the actual classical model being compared against, not from a default. The metric then answers "can the trained classical model be beaten", which is the real question.
3. Report the metric across a range of regularisation values, never as a single number.
4. Hold the setting fixed across every point in a published figure. The same kernel pair's g moves by more than five times across the plausible range, which would swamp any real difference between points.
5. If g comes out above √n, that means under-regularised, not "strong quantum separation". The code now issues a warning saying exactly that.

### 3.2 Two pessimistic guesses, both wrong

I flagged Python 3.13 on Apple Silicon as a risk, specifically that `qiskit-aer` would have no prebuilt wheel and that `qiskit-machine-learning` might not support 3.13. Both installed cleanly. We standardised on Python 3.13 as a result, matching your machine rather than forcing a downgrade.

### 3.3 A deprecated API that would have broken later

`ZZFeatureMap` as a class is deprecated in Qiskit 2.1 and scheduled for removal. The repo uses the function form instead, and CI now fails the build if a deprecated quantum API creeps back into the kernel path.

### 3.4 The two frameworks are not comparable on speed

Measured on identical work: Qiskit takes 9.0 milliseconds per kernel entry, PennyLane takes 2.2. That is a four-fold difference caused by the framework, not by anything about the kernels.

Consequence: any runtime comparison between a Qiskit kernel and a PennyLane kernel measures the framework. The paper's cost metric has to be **circuit evaluation counts**, which are framework-independent, with wall-clock reported separately and clearly labelled.

### 3.5 My own requirements file was not reproducible

The first draft used "version X or newer" for five packages. You and I followed the same file and ended up a pandas major version apart. In a project whose entire selling point is that a stranger can clone it and get the same answer, that was the wrong default sitting in the wrong file. Everything is now pinned exactly.

---

## 4. What we measured

### Cost, which sets the shape of the whole experiment

A quantum kernel over n data points needs roughly n²/2 circuit evaluations. At the measured rate:

| Data points | Circuit evaluations | Time to build one kernel |
| --- | --- | --- |
| 100 | 4,950 | 45 seconds |
| 250 | 31,125 | 4.7 minutes |
| 500 | 124,750 | 19 minutes |
| 284,807 (the full fraud dataset) | ~41 billion | ~12 years |

This is why cutting the data down for the quantum side is a hard constraint rather than a preference. It is arithmetic, not caution.

### Reproducibility, which came out better than planned

The same 75 tests and the same geometric difference values now hold across three combinations:

| Where | Python | Result |
| --- | --- | --- |
| Your MacBook Air, Apple Silicon | 3.13.15 | 75 passed, 82% coverage |
| Cloud container, Linux x86_64 | 3.11.15 | 75 passed, 82% coverage |
| GitHub runner, Linux x86_64 | 3.13 | 75 passed |

Different operating systems, different processor architectures, different underlying maths libraries, two Python versions. The geometric difference values agree to four significant figures. That matters more than it sounds: calculations built on eigenvalue decomposition do not always survive a change of maths library, and this one does.

### Speed of the demo

3 minutes 8 seconds on a GitHub runner, against a 30-minute budget. 160 seconds on your machine. The "clone and rerun in under 30 minutes" claim now has real headroom and is tested automatically on every push.

---

## 5. Decisions made, and who made them

| Decision | Outcome | Who |
| --- | --- | --- |
| Reuse the existing `qiskit-env` or build fresh | Build fresh, from a pinned requirements file | You, on my recommendation |
| Python version | 3.13 | Joint, after testing settled it |
| Repository name | `qml-benchmark-lab` | You |
| Public or private | Private until week 6 | You |
| Licence | Apache-2.0 | You, on my recommendation |
| How the regularisation strength is chosen | Derived from the classical model's own setting | Me, flagged for your review |
| Size limit for the quantum data | 500 points maximum | Me, forced by the cost arithmetic |
| How the reference classical kernel is picked | By kernel-target alignment, on training data only | Me, flagged for your review |

The last three are mine, and each is arguable. They are the ones you would have to defend to a reviewer, so they are worth disagreeing with now rather than later.

---

## 6. What is still open

**The pandas risk, deliberately deferred.** The test suite passes, but coverage shows the dataset loaders never ran. Pandas 3.0.5 has not executed a single line of this project. Week 2 finds out whether it behaves.

**IBM Quantum allocation.** The plan assumes roughly what the QAOA drift study saw, but IBM changed the Open Plan in March 2026. The hardware scope in week 10 depends on the real current number, and nobody has checked it.

**Pre-registration mechanism.** If the paper is going to claim the predicted direction was fixed before the results came in, GitHub commit dates are weak evidence because they are author-controlled. An OSF registration or a published hash is the credible version. Needs deciding before week 6, not after.

**A GitHub Actions warning.** Two actions target a Node version GitHub is retiring. Harmless now, a backlog item.

---

## 7. Week 2

Load the Telco churn dataset for the first time and find out what pandas 3.0 does to the loader. Then the fraud dataset, the splitting strategy, and the decision about how to handle the class imbalance.

The imbalance decision is the one to think about in advance. The obvious move is SMOTE, generating synthetic minority examples. I will argue against it, because it changes the geometry of the feature space, and the geometry is precisely what the geometric difference measures. Using it would confound the one thing this project exists to measure.
