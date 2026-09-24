"""The quantum kernel path: the frozen grid, the Gram cache, and resumability.

WHY THIS FILE EXISTS
--------------------
The quantum sweep is tens of hours across several nights. Three things would
cost days if they were wrong and nothing announced them:

  * the frozen grid silently differing from what docs/pre-registration.md
    registered;
  * the Gram cache returning a matrix computed for different inputs, which
    would corrupt every result downstream while looking fine;
  * a resumed run duplicating or skipping cells.

Everything here runs on synthetic data at 2 to 3 qubits, so CI needs no Kaggle
account and the suite stays fast.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from qbench.kernels.quantum import (
    FROZEN_SETTINGS,
    QuantumGramFactory,
    entries_without_cache,
    expected_entries,
    setting_label,
)

ROOT = Path(__file__).resolve().parents[1]
pytest.importorskip("pennylane")


# --- the frozen grid ------------------------------------------------------------

def test_frozen_grid_matches_the_pre_registration():
    """docs/pre-registration.md section 3: angle and IQP, one and two reps.
    If this fails, either the grid moved or the document did, and one of them
    is a deviation that has to be recorded."""
    assert len(FROZEN_SETTINGS) == 4
    assert {setting_label(p) for p in FROZEN_SETTINGS} == {
        "angle-r1", "angle-r2", "iqp-r1", "iqp-r2"}
    text = (ROOT / "docs" / "pre-registration.md").read_text()
    assert "angle embedding and IQP embedding, each at 1 and 2" in text
    assert "all four run" in text.lower()


def test_pre_registration_still_says_g_does_not_screen():
    text = (ROOT / "docs" / "pre-registration.md").read_text()
    assert "No setting is screened out before the sweep" in text


# --- the Gram cache -------------------------------------------------------------

def test_cache_returns_the_same_matrix_and_computes_once():
    f = QuantumGramFactory(2)
    k = f.gram_fn(dict(FROZEN_SETTINGS[0]))
    X = np.random.default_rng(0).uniform(0, np.pi, (6, 2))
    a = k(X)
    after_first = f.evaluations()
    b = k(X)
    assert np.array_equal(a, b)
    assert f.evaluations() == after_first, "a cache hit must not count as work"
    assert f.cache_hits() == 1


def test_cache_is_keyed_on_content_not_identity():
    """A re-derived but equal array must hit; a different array must not.
    A cache keyed on id() would silently return the wrong matrix after the
    caller rebuilt its inputs, which is the failure that would corrupt a run
    while looking perfectly healthy."""
    f = QuantumGramFactory(2)
    k = f.gram_fn(dict(FROZEN_SETTINGS[0]))
    X = np.random.default_rng(1).uniform(0, np.pi, (5, 2))
    k(X)
    k(X.copy())
    assert f.cache_hits() == 1

    other = X.copy()
    other[0, 0] += 0.5
    before = f.evaluations()
    k(other)
    assert f.evaluations() > before, "different data must be recomputed"


def test_cache_separates_settings_and_rectangular_blocks():
    f = QuantumGramFactory(2)
    rng = np.random.default_rng(2)
    X, Y = rng.uniform(0, np.pi, (5, 2)), rng.uniform(0, np.pi, (3, 2))
    k1 = f.gram_fn(dict(FROZEN_SETTINGS[0]))
    k2 = f.gram_fn(dict(FROZEN_SETTINGS[2]))
    assert not np.allclose(k1(X), k2(X)), "angle and IQP must differ"
    assert k1(Y, X).shape == (3, 5)
    assert f.cache_hits() == 0


def test_clear_frees_matrices_but_keeps_the_count():
    f = QuantumGramFactory(2)
    k = f.gram_fn(dict(FROZEN_SETTINGS[0]))
    X = np.random.default_rng(3).uniform(0, np.pi, (5, 2))
    k(X)
    n = f.evaluations()
    f.clear()
    k(X)
    assert f.evaluations() > n, "after clear the matrix is recomputed"


def test_gram_matrices_are_valid_kernels():
    f = QuantumGramFactory(3)
    X = np.random.default_rng(4).uniform(0, np.pi, (8, 3))
    for params in FROZEN_SETTINGS:
        K = f.gram_fn(dict(params))(X)
        assert K.shape == (8, 8)
        assert np.allclose(np.diag(K), 1.0, atol=1e-8), setting_label(params)
        assert np.allclose(K, K.T, atol=1e-8), setting_label(params)
        assert K.min() >= -1e-9 and K.max() <= 1 + 1e-9, setting_label(params)
        w = np.linalg.eigvalsh(K)
        assert w.min() > -1e-8, f"{setting_label(params)} not PSD: {w.min()}"


def test_cost_model_matches_how_the_runner_actually_calls_the_kernel():
    """Each setting gets its own tune_and_evaluate, so each needs its own test
    block; the cache saves the SECOND training Gram that evaluate recomputes
    after selection. An earlier version of this helper described a design where
    one call ranked all four settings, which is not what the runner does and
    would have mis-stated the budget."""
    n_tr, n_te = 100, 40
    per_train = n_tr * (n_tr - 1) // 2
    assert expected_entries(n_tr, n_te) == per_train + n_te * n_tr
    assert entries_without_cache(n_tr, n_te) == 2 * per_train + n_te * n_tr
    saving = 1 - expected_entries(n_tr, n_te) / entries_without_cache(n_tr, n_te)
    assert 0.2 < saving < 0.5


# --- resumability ---------------------------------------------------------------

def _run(tmp_path, *extra):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_quantum_kernels.py"),
         "--dataset", "synthetic", "--seeds", "0", "--mappings", "pca",
         "--qubits", "2", "--n-per-class", "12", "--out-dir", str(tmp_path), *extra],
        env=env, capture_output=True, text=True, timeout=900)


def test_dry_run_computes_nothing(tmp_path):
    proc = _run(tmp_path, "--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert "dry run: nothing computed" in proc.stdout
    assert not list(tmp_path.glob("*.jsonl"))


def test_resume_skips_completed_cells_and_never_duplicates(tmp_path):
    first = _run(tmp_path)
    assert first.returncode == 0, first.stderr
    out = tmp_path / "synthetic_matched_n12.jsonl"
    recs = [json.loads(line) for line in out.open()]
    assert len(recs) == 4, "four settings"
    assert {r["setting"] for r in recs} == {"angle-r1", "angle-r2", "iqp-r1", "iqp-r2"}

    second = _run(tmp_path)
    assert second.returncode == 0, second.stderr
    assert "nothing to do" in second.stdout
    assert len([json.loads(line) for line in out.open()]) == 4, "resume must not duplicate"


def test_a_truncated_final_line_is_repaired_not_tolerated(tmp_path):
    """What a laptop sleeping mid-write leaves behind.

    Skipping the bad line would be enough for this runner, and would leave the
    file unreadable by every analysis script, which call json.loads on every
    line. The run must repair the file, then refill what it dropped.
    """
    _run(tmp_path)
    out = tmp_path / "synthetic_matched_n12.jsonl"
    text = out.read_text()
    out.write_text(text[: -len(text.splitlines()[-1]) // 2])   # half a final record

    proc = _run(tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "repaired" in proc.stdout

    # every line valid JSON, no bare-except needed by any reader
    recs = [json.loads(line) for line in out.open()]
    assert {r["setting"] for r in recs} == {"angle-r1", "angle-r2", "iqp-r1", "iqp-r2"}
    assert len(recs) == 4, "the dropped record was recomputed, not lost or duplicated"


def test_shuffled_run_writes_a_separate_file(tmp_path):
    _run(tmp_path)
    _run(tmp_path, "--shuffle-labels")
    assert (tmp_path / "synthetic_matched_n12.jsonl").exists()
    assert (tmp_path / "synthetic_matched_n12_shuffled.jsonl").exists()
    real = json.loads((tmp_path / "synthetic_matched_n12.jsonl").open().readline())
    fake = json.loads((tmp_path / "synthetic_matched_n12_shuffled.jsonl").open().readline())
    assert real["shuffled"] is False and fake["shuffled"] is True


def test_records_carry_what_week_9_and_the_paper_need(tmp_path):
    _run(tmp_path)
    r = json.loads((tmp_path / "synthetic_matched_n12.jsonl").open().readline())
    assert len(r["test_decision_scores"]) == r["n_test"]
    assert r["test_label_fingerprint"]
    assert r["circuit_evaluations"] > 0, "cost is reported in circuit evaluations"
    assert r["device"] and r["embedding"] and r["reps"]


def test_runner_defaults_to_the_registered_backend():
    """The library default is `default.qubit`; the pre-registration registers
    `lightning.qubit` and the runner's cost model is measured on it. A dry run
    on 24 Sep 2026 printed a lightning-derived wall clock for a run that would
    have used default.qubit."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_quantum_kernels as rq  # noqa: PLC0415

    assert rq.REGISTERED_DEVICE == "lightning.qubit"
    text = (ROOT / "docs" / "pre-registration.md").read_text()
    assert "`lightning.qubit`" in text
    assert set(rq.MS_PER_ENTRY) == {4, 6, 8, 10, 12}, "cost model must cover the frozen sweep"


def test_unusable_device_refuses_rather_than_falling_back(tmp_path):
    proc = _run(tmp_path, "--device", "not.a.device", "--dry-run")
    assert proc.returncode != 0
    assert "deviation" in (proc.stdout + proc.stderr)
    assert not list(tmp_path.glob("*.jsonl"))
