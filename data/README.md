# Data provenance

Raw data is **not committed**. `data/raw/` and `data/processed/` are gitignored.
Fetch with the commands below, then check the SHA-256 against the recorded value:
Kaggle datasets can be revised in place, and a silent revision would change every
result downstream.

Retrieved 17 September 2026 with `kaggle` 2.2.4.

| Dataset | Kaggle slug | File | SHA-256 | Rows | Positives | Licence |
| --- | --- | --- | --- | --- | --- | --- |
| Telco Customer Churn | `blastchar/telco-customer-churn` | `WA_Fn-UseC_-Telco-Customer-Churn.csv` | `88be4b93fbe0cc83421af1c503794c97c342eca914c1576db7c276e61d61358a` | 7,043 raw / 7,032 loaded | 1,869 (0.2658) | copyright-authors |
| Credit Card Fraud (ULB) | `mlg-ulb/creditcardfraud` | `creditcard.csv` | `76274b691b16a6c49d3f159c883398e03ccd6d1ee12d9d8ee38f4b4b98551a89` | 284,807 | 492 (0.001727) | DbCL-1.0 |

## Fetch

```bash
kaggle datasets download -d blastchar/telco-customer-churn -p data/raw/churn --unzip
kaggle datasets download -d mlg-ulb/creditcardfraud    -p data/raw/fraud --unzip
shasum -a 256 data/raw/churn/*.csv data/raw/fraud/creditcard.csv
```

## Licences

The churn dataset is listed on Kaggle as `copyright-authors`, which does not grant
redistribution. This repository never redistributes it; users fetch it themselves.
The fraud dataset is under the Open Database Contents License (DbCL-1.0).

## Preprocessing decisions, and the evidence for each

**Churn.** `customerID` dropped. `TotalCharges` coerced to numeric; 11 rows are blank
and are dropped (7,043 to 7,032). Categoricals one-hot encoded with `drop_first=True`,
giving 30 features: 3 continuous, 27 binary.
Kept the one-hot columns: measured 17 Sep 2026, PCA on all 30 features at 3
dimensions retains 88.7% of available PR-AUC signal, against 77.1% for the 3
continuous features alone.

**Fraud.** `Time` dropped. It is seconds since the first transaction in a two-day
window, so it encodes row ordering rather than a property of the transaction.
Measured: removing it moves full-feature RBF SVM PR-AUC from 0.9593 to 0.9548.
`V1` to `V28` are already principal components, produced by the dataset authors
for anonymisation. Any further PCA is PCA on PCA.

## The quantum track does not see the full data

A quantum kernel over n points needs ~n²/2 circuit evaluations at ~9 ms each
(Qiskit, 4 qubits). The quantum track uses class-balanced subsamples of at most
~500 points. Fraud has only 492 positives, so its quantum subsamples use all of
them against a matched negative draw, and the original 0.17% base rate is not
preserved. Results are reported against the subsample's own base rate.
