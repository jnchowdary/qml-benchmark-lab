"""Tests for the four gaps found in the 22 Sep 2026 audit.

WHY THIS FILE EXISTS
--------------------
Three weeks of work produced a pipeline that met every acceptance criterion in
the plan and still could not have supported the paper it exists to produce.
The audit found six gaps; four are fixed here and tested here.

  gap 2  Per-test-point decision scores were never stored, so no paired test
         (McNemar, DeLong, paired bootstrap) could be run in week 9 without
         re-running every experiment.
  gap 3  Nobody had asked what effect size 10 seeds can resolve. The design
         might have been incapable of detecting any plausible quantum
         advantage, which would make a null result a statement about the
         experiment rather than about quantum kernels.
  gap 4  There was no negative control. Nothing in the suite would have caught
         a leak that inflated every result equally.
  gap 6  The cost model came from a Linux container and lightning.qubit had
         never been benchmarked, so every schedule rested on numbers from the
         wrong machine.

The shared cause: each week was checked against its own acceptance criteria
rather than against what week 9 and the paper would need. These tests are the
part of that lesson that can be made executable.

Everything here runs on the synthetic dataset, so CI needs no Kaggle account.
"""

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from qbench.data import SHUFFLE_SEED_OFFSET, balanced_subsample, load_dataset, make_split, shuffle_labels
from qbench.features import fit_mapping, scale_to_angles
from qbench.kernels.classical import build_classical_kernel
from qbench.tuning import evaluate, label_fingerprint, tune_and_evaluate

ROOT = Path(__file__).resolve().parents[1]
SMALL_C = (0.1, 1.0, 10.0)


@pytest.fixture(scope="module")
def prepared():
    X, y, _ = load_dataset("synthetic")
    Xs, ys = balanced_subsample(X, y, n_per_class=40, seed=0)
    X_tr, X_te, y_tr, y_te = make_split(Xs, ys, seed=0)
    Xm, transform = fit_mapping(X_tr, y_tr, 4, "pca", seed=0)
    Xa_tr, to_angles = scale_to_angles(Xm)
    return Xa_tr, to_angles(transform(X_te)), y_tr, y_te


def gram(name, **p):
    return build_classical_kernel(name, **p)


# --- gap 2: per-test-point decision scores --------------------------------------

def test_evaluate_stores_one_decision_score_per_test_point(prepared):
    X_tr, X_te, y_tr, y_te = prepared
    out = evaluate(gram("linear"), X_tr, y_tr, X_te, y_te, C=1.0)
    assert len(out["test_decision_scores"]) == len(y_te)
    assert len(out["test_labels"]) == len(y_te)
    assert all(isinstance(s, float) for s in out["test_decision_scores"])


def test_stored_scores_reproduce_the_reported_metric(prepared):
    """The stored scores must be the ones the headline number came from.

    If these drift apart, week 9's p-value describes a different model from
    week 3's table, and nothing would announce it.
    """
    from sklearn.metrics import average_precision_score, roc_auc_score

    X_tr, X_te, y_tr, y_te = prepared
    out = evaluate(gram("rbf", gamma=0.5), X_tr, y_tr, X_te, y_te, C=1.0)
    s, lab = out["test_decision_scores"], out["test_labels"]
    assert average_precision_score(lab, s) == pytest.approx(out["test_average_precision"], abs=1e-12)
    assert roc_auc_score(lab, s) == pytest.approx(out["test_roc_auc"], abs=1e-12)


def test_stored_labels_are_in_test_set_order(prepared):
    X_tr, X_te, y_tr, y_te = prepared
    out = evaluate(gram("linear"), X_tr, y_tr, X_te, y_te, C=1.0)
    assert out["test_labels"] == [int(v) for v in np.asarray(y_te).ravel()]


def test_fingerprint_is_order_sensitive():
    """Two records may only be paired if they were scored on the same points
    in the same order. A fingerprint that ignored order would license an
    invalid pairing."""
    y = np.array([0, 1, 1, 0, 1])
    assert label_fingerprint(y) == label_fingerprint(y.copy())
    assert label_fingerprint(y) != label_fingerprint(y[::-1])
    assert label_fingerprint(y) != label_fingerprint(np.array([0, 1, 1, 0, 0]))


def test_records_from_one_split_share_a_fingerprint(prepared):
    """Different kernels on the same split must agree, or pairing is invalid."""
    X_tr, X_te, y_tr, y_te = prepared
    a = tune_and_evaluate("linear", lambda p: gram("linear", **p), [{}],
                          X_tr, y_tr, X_te, y_te, seed=0, c_grid=SMALL_C)
    b = tune_and_evaluate("rbf", lambda p: gram("rbf", **p), [{"gamma": 0.5}],
                          X_tr, y_tr, X_te, y_te, seed=0, c_grid=SMALL_C)
    assert a["test_label_fingerprint"] == b["test_label_fingerprint"]
    assert len(a["test_decision_scores"]) == len(b["test_decision_scores"])


def test_record_survives_a_json_round_trip(prepared):
    """The record is written as JSONL. A numpy float in there fails at write
    time, after the expensive part of the run has already happened."""
    X_tr, X_te, y_tr, y_te = prepared
    rec = tune_and_evaluate("linear", lambda p: gram("linear", **p), [{}],
                            X_tr, y_tr, X_te, y_te, seed=0, c_grid=SMALL_C)
    back = json.loads(json.dumps(rec))
    assert back["test_decision_scores"] == rec["test_decision_scores"]


# --- gap 4: label-shuffled negative control -------------------------------------

def test_shuffle_preserves_class_counts():
    y = np.array([0] * 30 + [1] * 20)
    out = shuffle_labels(y, seed=3)
    assert np.bincount(out).tolist() == np.bincount(y).tolist()


def test_shuffle_is_deterministic_and_seed_dependent():
    y = np.array([0, 1] * 25)
    assert np.array_equal(shuffle_labels(y, 1), shuffle_labels(y, 1))
    assert not np.array_equal(shuffle_labels(y, 1), shuffle_labels(y, 2))


def test_shuffle_actually_moves_labels():
    y = np.array([0] * 25 + [1] * 25)
    assert not np.array_equal(shuffle_labels(y, 0), y)


def test_shuffle_offset_decouples_permutation_from_split_seed():
    """The permutation for seed s must not be the split RNG for seed s.

    If they shared a stream, the control would be correlated with the split it
    is supposed to be independent of, and no one could audit the difference.
    """
    y = np.array([0, 1] * 40)
    rng_same = np.random.default_rng(5)
    naive = np.asarray(y)[rng_same.permutation(len(y))]
    assert not np.array_equal(shuffle_labels(y, 5), naive)
    assert SHUFFLE_SEED_OFFSET > 0


def test_shuffled_labels_destroy_the_signal(prepared):
    """The control's whole purpose: on permuted labels the pipeline must score
    at chance. If this passes on real labels too, the experiment is measuring
    nothing."""
    X_tr, X_te, y_tr, y_te = prepared
    real = tune_and_evaluate("rbf", lambda p: gram("rbf", **p), [{"gamma": 0.5}],
                             X_tr, y_tr, X_te, y_te, seed=0, c_grid=SMALL_C)

    X, y, _ = load_dataset("synthetic")
    Xs, ys = balanced_subsample(X, y, n_per_class=40, seed=0)
    ys = shuffle_labels(ys, 0)
    Xs_tr, Xs_te, ys_tr, ys_te = make_split(Xs, ys, seed=0)
    Xm, transform = fit_mapping(Xs_tr, ys_tr, 4, "pca", seed=0)
    Xa_tr, to_angles = scale_to_angles(Xm)
    fake = tune_and_evaluate("rbf", lambda p: gram("rbf", **p), [{"gamma": 0.5}],
                             Xa_tr, ys_tr, to_angles(transform(Xs_te)), ys_te,
                             seed=0, c_grid=SMALL_C)

    assert real["test_roc_auc"] > 0.75, "synthetic data should be learnable"
    assert fake["test_roc_auc"] < 0.75, "shuffled labels must not be learnable"


# --- gap 3: minimum detectable effect -------------------------------------------

def _power_mod():
    sys.path.insert(0, str(ROOT / "scripts"))
    import power_analysis  # noqa: PLC0415
    return power_analysis


def test_mde_matches_a_known_value():
    """At sd=1, n=10, alpha=0.05, power=0.80 the required effect is d=0.9960.

    This constant was NOT taken from memory. The first version of this test
    asserted 0.9386 because that was what I recalled, the solver returned
    0.9960, and the simulation below settled it in favour of the solver
    (0.9386 delivers 75% power, not 80%). The lesson is the same one the audit
    produced: a remembered number is not evidence.
    """
    pa = _power_mod()
    assert pa.mde_paired_t(1.0, 10) == pytest.approx(0.9960, abs=0.002)


def test_mde_delivers_the_power_it_claims():
    """Simulate the test the MDE describes and count rejections.

    This is the check that makes the analytic solver trustworthy: if the
    non-centrality solve were wrong, every seed-count recommendation in the
    project would be wrong with it, and nothing else would notice.
    """
    pa = _power_mod()
    from scipy import stats as _stats

    for sd, n in ((1.0, 10), (0.05, 16)):
        mde = pa.mde_paired_t(sd, n)
        d = np.random.default_rng(0).normal(mde, sd, size=(40000, n))
        t = d.mean(1) / (d.std(1, ddof=1) / math.sqrt(n))
        power = float(np.mean(np.abs(t) > _stats.t.ppf(0.975, n - 1)))
        assert power == pytest.approx(0.80, abs=0.015), f"sd={sd} n={n} gave {power}"


def test_mde_beats_the_normal_approximation():
    """The familiar sd*(z+z)/sqrt(n) shortcut is optimistic at small n. If the
    exact solver ever returned the smaller number, it would be using the
    approximation by accident."""
    pa = _power_mod()
    sd, n = 0.1, 10
    normal = sd * (1.959964 + 0.841621) / math.sqrt(n)
    assert pa.mde_paired_t(sd, n) > normal


def test_mde_shrinks_with_more_seeds_and_grows_with_noise():
    pa = _power_mod()
    assert pa.mde_paired_t(0.1, 40) < pa.mde_paired_t(0.1, 10)
    assert pa.mde_paired_t(0.2, 10) > pa.mde_paired_t(0.1, 10)


def test_seeds_for_target_is_the_smallest_sufficient_n():
    pa = _power_mod()
    sd, target = 0.05, 0.03
    n = pa.seeds_for(sd, target)
    assert pa.mde_paired_t(sd, n) <= target
    assert pa.mde_paired_t(sd, n - 1) > target


def test_rank_test_floor_at_ten_pairs():
    """Hard limits week 9 cannot tune its way out of: with 10 pairs a
    two-sided sign test needs 9 wins, and Wilcoxon cannot go below p=0.002."""
    pa = _power_mod()
    sign_p, wins, wil_p = pa.rank_test_floor(10)
    assert sign_p == pytest.approx(2 / 1024)
    assert wins == 9
    assert wil_p == pytest.approx(0.001953, abs=1e-5)


# --- gap 6: backend selection ---------------------------------------------------

def test_pennylane_device_is_a_parameter_and_is_recorded():
    """The simulator used must be visible in the run metadata. A cost model
    measured on one backend and a run executed on another is how a schedule
    silently becomes wrong."""
    pytest.importorskip("pennylane")
    from qbench.kernels.pennylane_kernels import DEFAULT_DEVICE, build_pennylane_kernel

    k = build_pennylane_kernel(2, embedding="angle", reps=1)
    assert k.device_name == DEFAULT_DEVICE
    assert k.config["device"] == DEFAULT_DEVICE


def test_available_devices_never_returns_an_unusable_one():
    pytest.importorskip("pennylane")
    import pennylane as qml

    from qbench.kernels.pennylane_kernels import available_devices

    devs = available_devices()
    assert "default.qubit" in devs, "default.qubit ships with pennylane"
    for name in devs:
        qml.device(name, wires=2)  # must not raise
    assert "not.a.device" not in available_devices(candidates=("not.a.device", "default.qubit"))


def test_backends_that_disagree_are_not_a_speedup():
    """Every simulator here is exact, so a change of backend must not change
    the Gram matrix. A backend that is fast because it computes something else
    would otherwise look like a win."""
    pytest.importorskip("pennylane")
    from qbench.kernels.pennylane_kernels import available_devices, build_pennylane_kernel

    devs = available_devices()
    if len(devs) < 2:
        pytest.skip(f"only one usable pennylane device here: {devs}")
    X = np.random.default_rng(0).uniform(0, np.pi, size=(6, 3))
    ref = build_pennylane_kernel(3, device=devs[0]).evaluate(X)
    for name in devs[1:]:
        other = build_pennylane_kernel(3, device=name).evaluate(X)
        assert np.abs(np.asarray(ref) - np.asarray(other)).max() < 1e-8, name


def test_benchmark_script_runs_and_writes_its_json(tmp_path):
    """The benchmark is only useful if it survives a machine where an optional
    backend is missing. Run it small, with qiskit skipped."""
    pytest.importorskip("pennylane")
    out = tmp_path / "bench.json"
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "benchmark_backends.py"),
         "--qubits", "2", "--n", "6", "--repeats", "1", "--skip-qiskit", "--out", str(out)],
        env=env, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text())
    assert payload["results"], "no backend was timed"
    assert all(r.get("ms_per_entry", 0) >= 0 for r in payload["results"] if "ms_per_entry" in r)


# --- the 23 Sep design decisions, made executable -------------------------------

def test_training_size_sweep_writes_one_file_per_size(tmp_path):
    """Sizes must land in SEPARATE files. Every downstream analysis pairs
    records within a cell; a training size mixed into that pairing would be an
    invisible bug, because the records would look identical apart from a field
    nobody joined on."""
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_classical_baselines.py"),
         "--dataset", "synthetic", "--track", "matched", "--seeds", "0", "1",
         "--qubits", "4", "--mappings", "pca", "--n-per-class", "20", "40",
         "--out-dir", str(tmp_path)],
        env=env, capture_output=True, text=True, timeout=900,
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "synthetic_matched_n20.jsonl").exists()
    assert (tmp_path / "synthetic_matched_n40.jsonl").exists()
    small = [json.loads(line) for line in (tmp_path / "synthetic_matched_n20.jsonl").open()]
    big = [json.loads(line) for line in (tmp_path / "synthetic_matched_n40.jsonl").open()]
    assert {r["n_per_class"] for r in small} == {20}
    assert {r["n_per_class"] for r in big} == {40}
    assert small[0]["n_train"] < big[0]["n_train"]


def test_shuffled_run_never_overwrites_a_real_one(tmp_path):
    """A negative control written over a real result would be the single worst
    file-naming bug available to this project."""
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    base = ["--dataset", "synthetic", "--track", "matched", "--seeds", "0",
            "--qubits", "4", "--mappings", "pca", "--n-per-class", "20",
            "--out-dir", str(tmp_path)]
    for extra in ([], ["--shuffle-labels"]):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_classical_baselines.py")] + base + extra,
            env=env, capture_output=True, text=True, timeout=900)
        assert proc.returncode == 0, proc.stderr
    real = tmp_path / "synthetic_matched_n20.jsonl"
    fake = tmp_path / "synthetic_matched_n20_shuffled.jsonl"
    assert real.exists() and fake.exists()
    assert json.loads(real.open().readline())["shuffled"] is False
    assert json.loads(fake.open().readline())["shuffled"] is True


# --- the grid-edge diagnostic (week 4 gate) -------------------------------------

def _grid_mod():
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_grid_edges  # noqa: PLC0415
    return check_grid_edges


def test_extended_grid_strictly_contains_the_frozen_one():
    """If the extension were not a superset, the comparison would be between two
    different grids rather than a grid and its extension, and every conclusion
    drawn from it would be meaningless."""
    from qbench.tuning import matched_grids

    ge = _grid_mod()
    for d in (4, 8, 12):
        for direction in ("down", "up", "both"):
            base, ext = matched_grids(d), ge.extended_grids(d, direction)
            for kernel in ("rbf", "poly"):
                b = {ge._key(p) for p in base[kernel]}
                e = {ge._key(p) for p in ext[kernel]}
                assert b <= e, f"{kernel} d={d} {direction}: extension drops frozen points"
                assert len(e) > len(b), f"{kernel} d={d} {direction}: extension adds nothing"


def test_extension_reaches_both_edges():
    """The run flagged BOTH boundaries: gamma at its minimum and maximum, and
    degree at its maximum on fraud. A one-sided extension would answer half the
    question and then be reported as a clean result."""
    from qbench.tuning import matched_grids

    ge = _grid_mod()
    d = 8
    base, ext = matched_grids(d), ge.extended_grids(d, "both")
    seen = {ge.classify(p, base[k]) for k in ("rbf", "poly") for p in ext[k]}
    assert {"gamma-down", "gamma-up", "degree-up"} <= seen, seen


def test_classify_uses_set_membership_not_one_parameter():
    """A degree-6 point is outside the frozen grid even though its gamma is
    inside it. The first version of this diagnostic compared gamma alone and
    would have called that point 'inside'."""
    from qbench.tuning import matched_grids

    ge = _grid_mod()
    d = 8
    base = matched_grids(d)["poly"]
    inside_gamma = sorted({p["gamma"] for p in base})[2]
    assert ge.classify({"degree": 6, "gamma": inside_gamma, "coef0": 0.0}, base) == "degree-up"
    assert all(ge.classify(p, base) == "inside" for p in base)


def test_frozen_edge_detection_names_the_boundary():
    from qbench.tuning import matched_grids

    ge = _grid_mod()
    base = matched_grids(8)["poly"]
    gammas = sorted({p["gamma"] for p in base})
    degs = sorted({p["degree"] for p in base})
    assert "gamma-min" in ge.at_frozen_edge({"degree": degs[1], "gamma": gammas[0], "coef0": 0.0}, base)
    assert "degree-max" in ge.at_frozen_edge({"degree": degs[-1], "gamma": gammas[2], "coef0": 0.0}, base)
    assert ge.at_frozen_edge({"degree": degs[1], "gamma": gammas[2], "coef0": 0.0}, base) == []


def test_grid_edge_diagnostic_runs_end_to_end(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    out = tmp_path / "grid_edges.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_grid_edges.py"),
         "--dataset", "synthetic", "--seeds", "0", "--mappings", "pca",
         "--qubits", "4", "--n-per-class", "40", "--out", str(out)],
        env=env, capture_output=True, text=True, timeout=1800,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text())
    assert {s["kernel"] for s in payload["summaries"]} == {"rbf", "poly"}
    assert all(r["inner_extended"] >= r["inner_current"] - 1e-12 for r in payload["rows"]), \
        "a superset grid can never score worse than its subset"
