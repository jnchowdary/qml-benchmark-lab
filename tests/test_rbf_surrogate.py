"""The surrogate test's verdict logic, using the numbers that caught it out.

WHY THIS FILE EXISTS
--------------------
The first version of `rbf_surrogate.py` printed, on fraud's bandwidth arm:

    angle  n=40  quantum minus surrogate: +0.0002 [-0.0005, +0.0009]  p 0.0055
           the quantum kernel BEATS its own closest RBF. This is the only
           result in the project that could support quantum structure doing work.

The interval spans zero and the effect is 2e-04, five times below the 1e-03
reproducibility floor that deviations D2 established for every quantum result
here. D2 commits to reporting anything under that floor as below the pipeline's
arithmetic resolution rather than as a measurement. The verdict function checked
the Wilcoxon p-value and the sign, and nothing else: a rank test on forty
consistently-signed but trivially small differences rejects happily.

It also averaged iqp-r1 at +0.0852 [+0.0645, +0.1058] with iqp-r2 at -0.0493
[-0.0913, -0.0072] into a family effect of +0.0180 and reported "no detectable
difference", which is true of neither setting.

Both were caught by reading the output rather than by any test, which is the
reason they are tests now. Every case below is a real line from a real run.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import rbf_surrogate as rs  # noqa: E402


def e(mean, lo, hi, p, n=40):
    return {"n": n, "mean": mean, "ci": (lo, hi), "p_wilcoxon": p,
            "sd": abs(hi - lo) / 4 or 1e-6, "median": mean}


def ci_only(lo, hi, n=20):
    return {"embedding": "iqp", "normap": {"n": n, "ci": (lo, hi)}}


# ------------------------------------------- the three conditions, all required

def test_effect_below_the_precision_floor_is_never_a_finding():
    """fraud angle, bandwidth arm. The exact line that was misreported."""
    ok, why = rs._significant(e(0.0002, -0.0005, 0.0009, 0.0055))
    assert ok is False
    assert "precision floor" in why


def test_the_other_misreported_line_is_also_rejected():
    """fraud iqp, bandwidth arm: -0.0008, interval spanning zero, p 0.0224."""
    ok, why = rs._significant(e(-0.0008, -0.0019, 0.0004, 0.0224))
    assert ok is False


def test_interval_spanning_zero_is_not_a_finding_even_above_the_floor():
    ok, why = rs._significant(e(0.0040, -0.0010, 0.0090, 0.03))
    assert ok is False
    assert "spans zero" in why


def test_rank_test_must_also_reject():
    ok, why = rs._significant(e(0.0040, 0.0010, 0.0070, 0.20))
    assert ok is False
    assert "rank test does not reject" in why


def test_a_real_effect_passes_all_three():
    """churn iqp-r1 on the registered arm: +0.0852 [+0.0645, +0.1058], p 1.9e-06.
    Eighty-five times the precision floor with an interval nowhere near zero."""
    ok, why = rs._significant(e(0.0852, 0.0645, 0.1058, 1.91e-06, n=20))
    assert ok is True
    assert why == ""


def test_a_real_negative_effect_passes_too():
    """churn angle-r2, registered arm: -0.0162 [-0.0232, -0.0092], p 1.05e-04."""
    ok, _ = rs._significant(e(-0.0162, -0.0232, -0.0092, 1.05e-04, n=20))
    assert ok is True


@pytest.mark.parametrize("n", [0, 1])
def test_too_few_records_is_not_a_finding(n):
    ok, why = rs._significant(e(0.5, 0.4, 0.6, 0.001, n=n))
    assert ok is False


# --------------------------------------------- families must not average away

def test_non_overlapping_settings_block_a_family_verdict():
    """churn iqp, registered arm: the two settings point opposite ways with
    intervals that do not touch."""
    assert rs._heterogeneous([ci_only(0.0645, 0.1058), ci_only(-0.0913, -0.0072)])


def test_overlapping_settings_allow_a_family_verdict():
    assert not rs._heterogeneous([ci_only(-0.0095, 0.0033), ci_only(-0.0099, 0.0028)])


def test_family_reading_refuses_to_average_opposite_effects():
    reading = rs._reading("iqp", e(0.0180, -0.0132, 0.0492, 0.17),
                          [ci_only(0.0645, 0.1058), ci_only(-0.0913, -0.0072)])
    assert "no family-level effect" in reading
    assert "average of opposite effects" in reading


def test_real_finding_does_not_overclaim_advantage():
    """A kernel beating its own nearest RBF is not a kernel beating the best
    classical kernel. iqp-r1 did the first by +0.085 while losing the second by
    -0.101, and the wording has to keep those apart."""
    reading = rs._reading("iqp", e(0.0852, 0.0645, 0.1058, 1.91e-06, n=20), [])
    assert "NOT functionally an RBF" in reading
    assert "does NOT say it beats the best classical kernel" in reading.replace("It ", "")


def test_tight_null_and_wide_null_are_described_differently():
    tight = rs._reading("angle", e(0.0033, -0.0076, 0.0010, 0.0577), [])
    wide = rs._reading("iqp", e(0.0180, -0.0400, 0.0760, 0.60), [])
    assert "exclude an effect" in tight
    assert "absence of evidence" in wide


# ------------------------------------------------------- the floor is D2's

def test_precision_floor_matches_the_deviation_record():
    """D2 fixes this at roughly 1e-3 in average precision. If it is ever loosened
    here, the deviation record has to change with it."""
    assert rs.PRECISION_FLOOR == pytest.approx(1e-3)


def test_registered_rbf_range_matches_the_preregistration():
    assert rs.REGISTERED_RBF_RANGE == (1e-3, 1e2)


# ------------------------------------- the vectorised fit must be the same fit

def test_vectorised_gamma_fit_matches_the_reference_implementation():
    """The fit was rewritten to reuse one squared-distance matrix instead of
    calling rbf_kernel once per candidate gamma, because the all-cells
    replication runs it hundreds of times. A faster fit that lands on a
    different gamma would silently change every surrogate in the study."""
    import numpy as np
    from sklearn.metrics.pairwise import rbf_kernel
    from qbench.kernels.quantum import QuantumGramFactory

    rng = np.random.default_rng(0)
    X = rng.uniform(0.0, np.pi, size=(60, 8))
    K_q = QuantumGramFactory(8).gram_fn(
        {"embedding": "iqp", "reps": 1, "bandwidth": 1.0})(X)

    g_fast, rmse_fast = rs.fit_gamma(X, K_q)
    err_ref, g_ref = min((float(np.mean((rbf_kernel(X, gamma=float(g)) - K_q) ** 2)),
                          float(g)) for g in rs.FIT_GAMMAS)
    assert g_fast == g_ref
    assert rmse_fast == pytest.approx(float(np.sqrt(err_ref)))


def test_gamma_fit_uses_no_labels():
    """Stated as a test because it is the reason the surrogate is a fair
    comparison rather than a model tuned on its own score: fit_gamma's signature
    has no label argument at all."""
    import inspect
    assert set(inspect.signature(rs.fit_gamma).parameters) == {"Xa", "K_q", "sq"}


# ----------------------------------------------- Holm gating and replication

def test_holm_correction_can_veto_a_raw_effect():
    good = e(0.05, 0.03, 0.07, 0.001, n=20)
    assert rs.rs_significant_with_holm(good, 0.01)[0] is True
    ok, why = rs.rs_significant_with_holm(good, 0.40)
    assert ok is False
    assert "Holm" in why


def test_single_cell_effect_is_reported_as_unreplicated():
    """The churn iqp-r1 shape: one large positive cell, fourteen nulls."""
    primary = ("pca", 12)
    entries = [{"cell": primary, "n": 20, "gamma_median": 2.8,
                "e": e(0.0852, 0.0645, 0.1058, 1.91e-06, n=20)}]
    entries += [{"cell": ("selectk", q), "n": 20, "gamma_median": 2.0,
                 "e": e(0.0005, -0.004, 0.005, 0.7, n=20)} for q in (4, 6, 8, 10, 12)]
    adj = rs.holm([x["e"]["p_wilcoxon"] for x in entries])
    reading = rs._replication_reading("iqp-r1", entries, adj, primary, [entries[0]], [])
    assert "NO other cell" in reading
    assert "unreplicated" in reading


def test_broad_replication_is_reported_as_a_kernel_property():
    primary = ("pca", 12)
    entries = [{"cell": primary, "n": 20, "gamma_median": 2.8,
                "e": e(0.0852, 0.0645, 0.1058, 1e-06, n=20)}]
    entries += [{"cell": ("selectk", q), "n": 20, "gamma_median": 2.0,
                 "e": e(0.07, 0.05, 0.09, 1e-05, n=20)} for q in (4, 6, 8)]
    adj = rs.holm([x["e"]["p_wilcoxon"] for x in entries])
    reading = rs._replication_reading("iqp-r1", entries, adj, primary, entries, [])
    assert "property of the kernel" in reading


def test_nothing_to_replicate_when_the_primary_cell_is_null():
    primary = ("pca", 12)
    entries = [{"cell": primary, "n": 20, "gamma_median": 2.8,
                "e": e(0.0002, -0.0005, 0.0009, 0.0055, n=20)}]
    adj = rs.holm([x["e"]["p_wilcoxon"] for x in entries])
    reading = rs._replication_reading("iqp-r1", entries, adj, primary, [], [])
    assert "nothing here to replicate" in reading
