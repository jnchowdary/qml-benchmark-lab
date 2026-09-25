"""The small-bandwidth limit of a fidelity kernel is a classical RBF kernel.

WHY THIS IS LOAD BEARING
------------------------
The exploratory bandwidth arm closed the churn gap, and inner CV got there by
choosing bandwidths far below the registered 1.0. Whether that is a finding
about quantum kernels or a finding about what a quantum kernel degenerates into
depends entirely on the claim tested here, so the claim is not left as prose in
a script docstring.

    K_ij = prod_d cos^2(b * Delta_d / 2)
    log K = sum_d 2 log cos(b * Delta_d / 2) ~= -(b^2/4) * ||x - y||^2
    K -> exp(-gamma ||x-y||^2)  with  gamma = (reps * b)^2 / 4

If this is right, then at the selected bandwidths the quantum kernel is a kernel
the classical arm has been searching since week 2, and no advantage claim can
rest on it. The tolerances below are the measured agreement, not aspirations.
"""

import sys
from pathlib import Path

import numpy as np
import pytest
from scipy import stats
from sklearn.metrics.pairwise import rbf_kernel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from qbench.kernels.quantum import QuantumGramFactory  # noqa: E402
from classical_limit import offdiag, predicted_gamma  # noqa: E402


def angle_gram(X, nq, bandwidth, reps=1):
    f = QuantumGramFactory(nq)
    return f.gram_fn({"embedding": "angle", "reps": reps, "bandwidth": bandwidth})(X)


@pytest.fixture(scope="module")
def X12():
    rng = np.random.default_rng(0)
    return rng.uniform(0.0, np.pi, size=(50, 12))


def test_predicted_gamma_accounts_for_reps():
    """reps multiplies the effective angle, so it multiplies b before squaring."""
    assert predicted_gamma(1, 0.5) == pytest.approx(0.0625)
    assert predicted_gamma(2, 0.25) == predicted_gamma(1, 0.5)


# The bandwidths inner CV actually selected on churn, with the agreement measured
# at 12 qubits. 58 of 80 records chose one of the first two.
@pytest.mark.parametrize("bw,max_diff", [(0.0625, 1e-4), (0.125, 1e-3), (0.25, 1e-2)])
def test_selected_bandwidths_are_an_rbf_kernel(bw, max_diff, X12):
    K_q = angle_gram(X12, 12, bw)
    K_r = rbf_kernel(X12, gamma=predicted_gamma(1, bw))
    assert np.abs(K_q - K_r).max() < max_diff


@pytest.mark.parametrize("bw,rho_min", [(0.0625, 0.99999), (0.125, 0.99999),
                                        (0.25, 0.9999), (0.5, 0.999)])
def test_orderings_are_identical_below_the_registered_bandwidth(bw, rho_min, X12):
    """The decisive form of the claim. Deviations D2 established that both
    registered endpoints are rank statistics with a precision floor near 1e-3 in
    average precision, so two kernels that rank every pair the same way are the
    same kernel for everything this project measures."""
    K_q = angle_gram(X12, 12, bw)
    K_r = rbf_kernel(X12, gamma=predicted_gamma(1, bw))
    rho = stats.spearmanr(offdiag(K_q), offdiag(K_r)).statistic
    assert rho > rho_min


def test_the_registered_bandwidth_is_genuinely_not_an_rbf_kernel(X12):
    """The contrast that makes the finding a finding rather than a tautology: at
    the REGISTERED bandwidth the kernel is measurably distinct from its nearest
    RBF, so the convergence above is a property of small bandwidth and not of
    fidelity kernels in general."""
    K_q = angle_gram(X12, 12, 1.0)
    K_r = rbf_kernel(X12, gamma=predicted_gamma(1, 1.0))
    rho = stats.spearmanr(offdiag(K_q), offdiag(K_r)).statistic
    assert np.abs(K_q - K_r).max() > 1e-2
    assert rho < 0.99


def test_agreement_improves_monotonically_as_bandwidth_falls(X12):
    """A limit, not a coincidence at one value."""
    diffs = [np.abs(angle_gram(X12, 12, b)
                    - rbf_kernel(X12, gamma=predicted_gamma(1, b))).max()
             for b in (1.0, 0.5, 0.25, 0.125, 0.0625)]
    assert diffs == sorted(diffs, reverse=True)


@pytest.mark.parametrize("nq", [8, 12])
def test_the_limit_does_not_depend_on_qubit_count(nq):
    """gamma = b^2/4 carries no n, so the collapse is not something the qubit
    count can be blamed for or credited with."""
    rng = np.random.default_rng(1)
    X = rng.uniform(0.0, np.pi, size=(40, nq))
    K_q = angle_gram(X, nq, 0.0625)
    K_r = rbf_kernel(X, gamma=predicted_gamma(1, 0.0625))
    assert np.abs(K_q - K_r).max() < 1e-4


def test_registered_bandwidth_concentrates_toward_the_haar_floor(X12):
    """The mechanism on the other side, and why the registered kernel failed:
    at bandwidth 1.0 on 12 qubits the mean off-diagonal fidelity is far below
    the small-bandwidth regime and heading for 2^-n."""
    mean_reg = offdiag(angle_gram(X12, 12, 1.0)).mean()
    mean_sel = offdiag(angle_gram(X12, 12, 0.0625)).mean()
    assert mean_reg < 0.10
    assert mean_sel > 0.95


# ------------------------------ the reading must not generalise across families

def test_family_reading_is_per_family_not_blanket():
    """The first version of classical_limit.py computed agreement over the angle
    family and then printed one verdict about 'the selected quantum kernel'. On
    churn, five of eight seeds had chosen IQP, whose worst Spearman was 0.895, so
    the verdict was wrong for the majority of the rows it covered. A conclusion
    drawn from a subset and stated over the whole is the exact failure this
    project exists to avoid, so it is now a test."""
    import classical_limit as cl
    rows = [{"embedding": "angle", "spearman_offdiag_vs_best_fit": 0.999999,
             "rmse_best_fit_rbf": 1e-5}] * 3 + \
           [{"embedding": "iqp", "spearman_offdiag_vs_best_fit": 0.895,
             "rmse_best_fit_rbf": 1e-1}] * 5
    angle = cl._family_reading(rows, "angle")
    iqp = cl._family_reading(rows, "iqp")
    assert "IS the classical limit" in angle
    assert "NOT the classical limit" in iqp
    assert "3/8" in angle and "5/8" in iqp


def test_family_reading_handles_an_absent_family():
    import classical_limit as cl
    rows = [{"embedding": "angle", "spearman_offdiag_vs_best_fit": 1.0,
             "rmse_best_fit_rbf": 0.0}]
    assert "not selected" in cl._family_reading(rows, "iqp")
