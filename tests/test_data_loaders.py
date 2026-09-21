"""Loader tests on small synthetic CSVs shaped like the real files.

The real datasets need a Kaggle account, so CI cannot fetch them. These fixtures
reproduce the specific quirks the loaders must handle: blank TotalCharges strings
in churn, the Time column in fraud, and the pandas 3.0 get_dummies bool dtype.
"""

import numpy as np
import pandas as pd
import pytest

from qbench.data import load_dataset


@pytest.fixture
def churn_root(tmp_path):
    d = tmp_path / "raw" / "churn"
    d.mkdir(parents=True)
    pd.DataFrame({
        "customerID": ["a", "b", "c", "d", "e", "f"],
        "gender": ["Male", "Female", "Male", "Female", "Male", "Female"],
        "SeniorCitizen": [0, 1, 0, 0, 1, 0],
        "tenure": [1, 34, 2, 45, 8, 22],
        "Contract": ["Month-to-month", "One year", "Month-to-month",
                     "Two year", "Month-to-month", "One year"],
        "MonthlyCharges": [29.85, 56.95, 53.85, 42.30, 99.65, 89.10],
        "TotalCharges": ["29.85", "1889.5", " ", "1840.75", "820.5", "1949.4"],
        "Churn": ["No", "No", "Yes", "No", "Yes", "No"],
    }).to_csv(d / "WA_Fn-UseC_-Telco-Customer-Churn.csv", index=False)
    return tmp_path


@pytest.fixture
def fraud_root(tmp_path):
    d = tmp_path / "raw" / "fraud"
    d.mkdir(parents=True)
    rng = np.random.default_rng(0)
    n = 20
    df = pd.DataFrame({"Time": np.arange(n, dtype=float)})
    for i in range(1, 29):
        df[f"V{i}"] = rng.normal(size=n)
    df["Amount"] = rng.uniform(0, 500, n)
    df["Class"] = [1, 0] * (n // 2)
    df.to_csv(d / "creditcard.csv", index=False)
    return tmp_path


def test_churn_drops_blank_total_charges(churn_root):
    X, y, _ = load_dataset("churn", data_root=churn_root)
    assert len(X) == 5  # one of six rows has a blank TotalCharges


def test_churn_output_is_float_after_get_dummies(churn_root):
    """pandas >= 2 returns bool dummies; the loader must still hand back float."""
    X, _, _ = load_dataset("churn", data_root=churn_root)
    assert X.dtype == np.float64
    assert np.isfinite(X).all()


def test_churn_drops_id_and_target(churn_root):
    _, _, names = load_dataset("churn", data_root=churn_root)
    assert "customerID" not in names and "Churn" not in names


def test_churn_one_hot_uses_drop_first(churn_root):
    _, _, names = load_dataset("churn", data_root=churn_root)
    assert "gender_Male" in names and "gender_Female" not in names


def test_churn_labels_are_binary(churn_root):
    _, y, _ = load_dataset("churn", data_root=churn_root)
    assert set(np.unique(y)) <= {0, 1}
    assert y.sum() == 1  # the blank-TotalCharges row was one of the two churners


def test_fraud_drops_time(fraud_root):
    """Time encodes row ordering; measured to contribute 0.0045 PR-AUC."""
    _, _, names = load_dataset("fraud", data_root=fraud_root)
    assert "Time" not in names


def test_fraud_shape_and_columns(fraud_root):
    X, y, names = load_dataset("fraud", data_root=fraud_root)
    assert X.shape == (20, 29)          # 28 V columns + Amount
    assert names[0] == "V1" and names[-1] == "Amount"
    assert "Class" not in names
    assert y.sum() == 10


def test_missing_file_gives_fetch_instructions(tmp_path):
    with pytest.raises(FileNotFoundError, match="kaggle datasets download"):
        load_dataset("fraud", data_root=tmp_path)


def test_unknown_dataset_raises():
    with pytest.raises(ValueError, match="Unknown dataset"):
        load_dataset("iris")
