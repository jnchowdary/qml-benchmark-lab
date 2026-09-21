# QML Benchmark Lab: Week 2 Record

Written 21 September 2026. Covers work done 17 to 21 September 2026.
Commit `3965f29` on `main`. CI run 35598350514 green.

---

## 1. What week 2 was for

Week 2 was the data layer: get both real datasets loading, prove that train/test splits are reproducible bit-for-bit, record where the data came from, and settle the preprocessing decisions with evidence rather than argument.

The plan's acceptance criterion was that two runs of the same seed produce byte-identical splits. That criterion is met and is now enforced by tests on every push.

One risk was carried in from week 1 on purpose. Pandas 3.0.5 had never executed a line of this project, because the dataset loaders were only exercised once real data existed. Week 1's 75 passing tests said nothing about it: coverage on `data.py` sat at 62%, and the missing lines were exactly the loaders.

---

## 2. The datasets

| | Telco Customer Churn | Credit Card Fraud (ULB) |
| --- | --- | --- |
| Kaggle slug | `blastchar/telco-customer-churn` | `mlg-ulb/creditcardfraud` |
| File | `WA_Fn-UseC_-Telco-Customer-Churn.csv` (977 KB) | `creditcard.csv` (150.8 MB) |
| Raw rows | 7,043 | 284,807 |
| Rows after loading | 7,032 | 284,807 |
| Features after loading | 30 (3 continuous, 27 binary) | 29 (after dropping `Time`) |
| Positives | 1,869 (0.2658) | 492 (0.001727) |
| Licence | copyright-authors (no redistribution) | DbCL-1.0 |
| SHA-256 | `88be4b93fbe0cc83421af1c503794c97c342eca914c1576db7c276e61d61358a` | `76274b691b16a6c49d3f159c883398e03ccd6d1ee12d9d8ee38f4b4b98551a89` |

Both retrieved 17 September 2026 with `kaggle` 2.2.4. The checksums matter because Kaggle datasets can be revised in place, and a silent revision would change every downstream number with nothing to flag it. They are recorded in `data/README.md`.

Raw data is never committed. `data/raw/` is gitignored, and the churn licence does not permit redistribution in any case. Anyone reproducing the work fetches the files themselves and checks the hash.

### Pandas 3.0: cleared

Both loaders ran correctly first time under pandas 3.0.5. Churn exercised `read_csv`, `to_numeric(errors='coerce')`, `dropna`, `df.pop` and `get_dummies` in sequence; the bool dummies pandas now returns cast cleanly to float64. The 11 dropped churn rows are the dataset's known quirk: `TotalCharges` is a blank string for customers with zero tenure.

### A loose end on credentials

Moving `kaggle.json` from Downloads failed with "no such file", yet the download authenticated anyway. Your Kaggle credentials already live somewhere on the machine and neither of us knows where. Harmless today, but worth finding before the token expires.

---

## 3. The question that decided the week: does signal survive the squeeze?

The quantum track can afford 2 to 8 qubits, meaning 2 to 8 features. Churn arrives as 30 columns and fraud as 29. If squeezing those down to a handful of dimensions destroys the predictive signal, then every kernel comparison at low qubit counts measures noise. A null quantum result would then be an artefact of the representation, not a finding about quantum kernels, and no test would catch it.

So we measured it before building on it. `scripts/diagnose_representation.py` fits a plain classical RBF SVM on each candidate representation and scores PR-AUC against two anchors:

- **Baseline**: the positive class rate, which is what a useless model scores.
- **Full**: an SVM on all features with no reduction, the ceiling.

The "% of full" column is the share of available signal that survives the reduction.

### Churn

Baseline 0.2659, full 0.6053, headroom 0.3394.

| Mapping | 2 qubits | 3 | 4 | 6 | 8 |
| --- | --- | --- | --- | --- | --- |
| PCA | 87.2% | 88.7% | 92.7% | 94.4% | 95.0% |
| SelectKBest (mutual information) | 90.0% | 93.3% | 74.8% | 82.6% | 91.1% |
| Random projection (RFF) | 33.1% | 66.6% | 76.4% | 85.1% | 82.9% |

Controls: the 3 continuous features alone, unreduced, 77.1%. The same 3 reduced to 2 dimensions, 76.7%.

### Fraud

Class-balanced sample of 2,492 rows (all 492 positives, 2,000 negatives). Baseline 0.1979, full 0.9548, headroom 0.7569.

| Mapping | 2 qubits | 3 | 4 | 6 | 8 |
| --- | --- | --- | --- | --- | --- |
| PCA | 92.3% | 93.5% | 93.7% | 93.6% | 92.9% |
| SelectKBest (mutual information) | 97.8% | 98.1% | 98.6% | 98.9% | 99.2% |
| Random projection (RFF) | 74.7% | 80.8% | 91.1% | 92.2% | 82.2% |

---

## 4. What the measurements established

### 4.1 The representation is viable

At 4 qubits, churn PCA keeps 92.7% of available signal and fraud SelectKBest keeps 98.6%. The kernel comparison will measure something real. The worst outcome for the week, a dead representation at low qubit counts, did not happen.

### 4.2 Churn's one-hot columns stay

I had argued the 27 one-hot binaries might be noise: standardising binaries inflates rare categories, and PCA on a mix of inflated binaries and real continuous features could be dominated by whichever happened to carry variance. The control disproved it. The 3 continuous features alone reach 77.1%; PCA on all 30 at the same 3 dimensions reaches 88.7%. The one-hot columns carry roughly 11 points of real signal. They stay, decided by evidence against the position I had been arguing.

### 4.3 Signal saturates early

Churn reaches 87% of available signal at 2 qubits and gains only about 8 more points by 8. Fraud PCA peaks at 4 qubits and then declines slightly. Both datasets carry only a few dimensions of usable structure, however many columns they have.

Two consequences. The plan's `{4, 6, 8}` qubit sweep buys very little. And low qubit counts are viable, which matters a great deal for week 10: a 4-qubit hardware run against a limited QPU allowance is far more realistic than 8.

### 4.4 The best mapping inverts between datasets

On churn, PCA beats SelectKBest. On fraud the reverse holds cleanly: SelectKBest runs 97.8% to 99.2%, rising steadily, while PCA sits at 92.3% to 93.7% and declines past 4 qubits.

The likely mechanism: fraud's `V1` to `V28` are already principal components, created by the dataset authors to anonymise the original features. They are ordered by variance in the original feature space, and that ordering says nothing about fraud. Our PCA truncates by variance, so it discards predictive components that happen to sit low in the ordering. Mutual-information selection picks components by how well they predict the label. On a dataset that arrives pre-PCA'd, a second PCA is close to the worst available choice.

This makes the mapping a genuine experimental factor, not a preprocessing detail. It also connects to the Schaeffler/FAU result that dataset choice explained 73% of their variance against 9% for kernel type.

### 4.5 SelectKBest is non-monotone on churn

90.0% at 2 qubits, 93.3% at 3, then down to 74.8% at 4 before climbing back. Adding a feature makes it worse. This is a known weakness of univariate selection: each feature is scored in isolation, so a fourth feature redundant with the first three still ranks well. This drop is reproducible (see section 5), so it belongs in the methods section as a caveat, not dismissed as noise.

### 4.6 Random projection is dominated but kept

RFF is the weakest mapping everywhere, at 33.1% on churn at 2 qubits. It stays as a control, because it shows that mapping choice moves results more than kernel choice does.

---

## 5. The bug: a non-deterministic mapping

**What happened.** The same diagnostic, run twice on identical data with an identical seed, gave churn SelectKBest at 4 qubits a PR-AUC of 0.5199 the first time and 0.5664 the second.

**Cause.** `SelectKBest(mutual_info_classif, ...)` in `features.py`. `mutual_info_classif` estimates mutual information with a nearest-neighbour method, and it breaks ties between identical continuous values by adding a little random noise. That noise is controlled by a `random_state` argument we never set, so it defaulted to `None` and drew fresh noise on every call. Every other random source in the project takes our seed. This one hid behind a bare function reference, so the seed had no obvious way to reach it.

**Fix.** `functools.partial(mutual_info_classif, random_state=seed)` fixes the seed on the scoring function before `SelectKBest` ever calls it.

**How it survived.** The 75-test suite passed throughout. It explicitly tested reproducibility elsewhere but never called `fit_mapping`, so `features.py` sat at 62% coverage with the mapping functions untested. The pass count said all was well; coverage showed why it wasn't. **The lesson carried forward: coverage is the number to read, not the pass count.**

**Verified.** Two consecutive full diagnostic runs, diffed, are byte-identical. `test_reproducibility.py` now guards it on every push.

---

## 6. The fraud `Time` column: dropped

`Time` is seconds elapsed since the first transaction in a two-day window. It describes when a row sits in the file, not anything about the transaction, and would not carry over to any other period.

Measured: dropping it moves full-feature PR-AUC from 0.9593 to 0.9548, a change of 0.0045. It contributes almost nothing, and what little it does add is a timing artefact. It is now dropped inside the loader, and the reason is written into the code.

A useful side check: the diagnostic results with the loader dropping `Time` match the earlier run where it was dropped by hand, to four decimal places. The loader change does exactly what it claims.

---

## 7. Fixes to the diagnostic script itself

The diagnostic needed four corrections. Each would have produced misleading output without any error.

| Defect | Effect | Fix |
| --- | --- | --- |
| Control guarded by `len(continuous) >= min(qubits)`, i.e. 3 ≥ 4 | The key control row silently never ran | Control runs regardless of the qubit list |
| No row cap | On fraud, RBF SVM is roughly O(n²) in training rows; about 199,000 rows would run for hours with no sign of progress | `--max-rows`, default 4,000, class-balanced, with a printed warning that the base rate has changed |
| Footer text specific to churn ("the 26 binary columns") | Misleading instructions printed under fraud results | Footer made dataset-neutral |
| Continuous-feature list matched only `Amount` on fraud | A meaningless one-feature "control" at 14.3% | Control runs only where one-hot columns exist to be questioned |

---

## 8. Tests and coverage

| | End of week 1 | End of week 2 |
| --- | --- | --- |
| Tests | 75 | 106 |
| Total coverage | 82% | 94% |
| `data.py` | 62% | 98% |
| `features.py` | 62% | 97% |

**`tests/test_reproducibility.py`**, 17 tests. Splits bit-identical across calls. Different seeds give different splits, which guards against a seed being silently ignored and quietly wrecking the 10-seed design. Every mapping deterministic, including its fitted transform. Angle values stay inside `[0, π]`, because values outside it wrap around the Bloch sphere and make distant points look similar, producing a kernel that passes every check and means nothing. The angle scaler is fit on training data only; leakage here changes the quantum circuits themselves, not just a decision boundary.

**`tests/test_data_loaders.py`**, 9 tests. Uses small fake CSVs that copy the real files' quirks: a blank `TotalCharges`, the `Time` column, pandas 3.0 bool dummies. So the loader code runs in CI on every push with no Kaggle account, on a second platform. Until now it had only ever run on your laptop.

---

## 9. Housekeeping

- `data/README.md`: sources, checksums, licences, fetch commands, and the measured evidence for each preprocessing decision.
- `.DS_Store` added to `.gitignore`. Six macOS Finder files were about to go into the commit.
- Staging guard before committing: `git diff --cached --name-only | grep data/raw`, so 150 MB of raw data cannot reach the history, where removing it would mean rewriting commits.
- Commit `3965f29`: 7 files, 483 lines added. 9.47 KiB pushed, itself confirmation that no data went with it.

### Process failures on my side, recorded honestly

- A remote file write reported success and did not land. I now edit your files directly and check the result.
- A patch guard checked for `random_state=seed`, which already appeared on the PCA line, so it reported "already patched" and changed nothing. Caught by inspecting the file afterwards.
- Running `git status` from my side left an empty `.git/index.lock` that I could not delete, which would have blocked your next git command. You removed it. I no longer run git on your repository.

All three failed silently. Each was caught only because the result was checked, not trusted.

---

## 10. Decisions

| Decision | Outcome | Basis |
| --- | --- | --- |
| Churn one-hot columns | Keep | Measured: 88.7% vs 77.1% without them |
| Fraud `Time` column | Drop | Measured: contributes 0.0045 PR-AUC, and it is an ordering artefact |
| Mapping | An experimental factor; carry both PCA and SelectKBest on both datasets | Measured inversion between datasets |
| Seed on mutual information | Required | Measured non-determinism |
| Fraud quantum subsample | All 492 positives against matched negatives; report against the subsample's own base rate | 492 positives cannot support the real 0.17% rate within a ~500-point budget |

### Proposed, awaiting your decision

- **Qubit sweep of `{2, 4, 8}` instead of `{4, 6, 8}`.** Signal saturates early, so three points spanning the range tell us more than five clustered where nothing changes. That gives 2 datasets × 3 mappings × 3 qubit counts = 18 cells for the geometric-difference pre-screen.
- **No SMOTE in the main pipeline.** Synthetic minority points change the geometry of the feature space, and geometry is what g measures. The proposal is stratified subsampling plus `class_weight='balanced'`, with SMOTE only as a labelled appendix ablation if a reviewer asks.

---

## 11. Still open

- **IBM Quantum allocation.** Not yet checked against the March 2026 Open Plan change. Week 10's hardware scope depends on it.
- **Pre-registration mechanism.** OSF registration or a published hash, decided before week 6. GitHub commit dates are weak evidence because the author controls them.
- **Kaggle credential location.** Unknown, as noted above.
- **GitHub Actions Node 20 warning.** Harmless for now.
- **`classical.py` lines 47 to 53.** The reference-kernel selection loop, first exercised properly in week 6.

---

## 12. Week 3

Week 3 is the classical baselines: linear, RBF, polynomial, and the random-projection comparator, each tuned by nested cross-validation.

The position going in: under-tuning the classical side is the most common way papers in this area produce an apparent quantum advantage. The failure is quiet. An RBF SVM left at default `gamma` loses to a carefully tuned quantum kernel, and it looks like a finding. The classical grid should therefore be wider and more carefully cross-validated than the quantum one, which is the opposite of where effort naturally goes.
