"""The two-primary-endpoint rule, and what it costs.

WHY THIS FILE EXISTS
--------------------
The pre-registration declares average precision and ROC-AUC as co-primary.
"Co-primary" means two different things: either endpoint may succeed (union,
needs alpha split) or both must (intersection-union, needs no correction but
must clear twice). The second is only cheap if the two tests are correlated,
which is an empirical question, so the cost is simulated from the measured
correlation rather than assumed.
"""

import math
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import endpoint_correlation as ec  # noqa: E402
from power_analysis import mde_paired_t  # noqa: E402


def test_perfect_correlation_costs_nothing():
    """If the two endpoints always agree, demanding both is the same test
    twice and the effect needed is unchanged."""
    single = mde_paired_t(0.02, 20, alpha=0.05)
    both = ec.iu_mde(0.02, 20, rho=1.0, n_sim=20000)
    assert both == pytest.approx(single, rel=0.05)


def test_cost_rises_as_the_endpoints_disagree():
    vals = [ec.iu_mde(0.02, 20, rho=r, n_sim=20000) for r in (0.99, 0.8, 0.4, 0.0)]
    assert vals == sorted(vals), vals
    assert vals[-1] > vals[0] * 1.1


def test_independent_endpoints_are_worse_than_splitting_alpha():
    """At rho=0 the intersection-union rule is the expensive one, which is why
    the choice has to be made from the measured correlation and not from a
    preference for the rule that needs no correction."""
    union = mde_paired_t(0.02, 20, alpha=0.025)
    assert ec.iu_mde(0.02, 20, rho=0.0, n_sim=20000) > union


def test_simulated_rule_delivers_the_power_it_claims():
    """Guards the simulator itself: draw at the reported MDE and count joint
    rejections."""
    sd, n, rho = 0.02, 20, 0.9
    mde = ec.iu_mde(sd, n, rho, n_sim=20000)
    rng = np.random.default_rng(7)
    z1 = rng.standard_normal((40000, n))
    z2 = rho * z1 + math.sqrt(1 - rho ** 2) * rng.standard_normal((40000, n))
    z = np.stack([z1, z2], axis=2) + mde / sd
    t = z.mean(axis=1) / (z.std(axis=1, ddof=1) / math.sqrt(n))
    crit = stats.t.ppf(0.975, n - 1)
    power = float(np.mean((t[:, 0] > crit) & (t[:, 1] > crit)))
    assert power == pytest.approx(0.80, abs=0.02)


def test_pairs_are_aligned_on_seed_not_list_order():
    """A silent misalignment between the two metrics would give a correlation
    that means nothing and looks plausible. Records are fed in shuffled order
    on purpose."""
    recs = []
    for seed in range(6):
        for method, ap, roc in (("linear", 0.80 + seed * 0.01, 0.70 + seed * 0.01),
                                ("rbf", 0.70 + seed * 0.01, 0.60 + seed * 0.01)):
            recs.append({"mapping": "pca", "n_qubits": 4, "seed": seed, "method": method,
                         "test_average_precision": ap, "test_roc_auc": roc})
    rng = np.random.default_rng(0)
    rng.shuffle(recs)
    rows = ec.paired_pairs(recs)[("pca", 4)]["linear-rbf"]
    assert len(rows) == 6
    for seed, d_ap, d_roc in rows:
        assert d_ap == pytest.approx(0.10)
        assert d_roc == pytest.approx(0.10)


def test_correlation_of_identical_series_is_one():
    recs = []
    rng = np.random.default_rng(1)
    for seed in range(10):
        a = float(rng.normal())
        recs.append({"mapping": "pca", "n_qubits": 4, "seed": seed, "method": "linear",
                     "test_average_precision": 0.8 + a, "test_roc_auc": 0.7 + a})
        recs.append({"mapping": "pca", "n_qubits": 4, "seed": seed, "method": "rbf",
                     "test_average_precision": 0.8, "test_roc_auc": 0.7})
    assert ec.correlations(recs)[0] == pytest.approx(1.0, abs=1e-9)
