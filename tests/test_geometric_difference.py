"""Property tests for g(K_C || K_Q).

There is no published reference *value* to check against without reprinting
someone's results, so these tests pin the metric's mathematical properties
instead. If a refactor breaks any of these, the metric is wrong and every
downstream figure in the paper is wrong with it.
"""

import warnings

import numpy as np
import pytest

from qbench.kernels.geometric_difference import (
    g_lambda_sweep,
    geometric_difference,
    geometric_difference_regularised,
    interpret_g,
    geometric_difference_training,
    lambda_from_svm_C,
    normalise_kernel,
)


def random_psd_kernel(n, rank=None, seed=0):
    """A random PSD Gram matrix with unit diagonal (a valid fidelity-like kernel)."""
    rng = np.random.default_rng(seed)
    rank = rank or n
    A = rng.normal(size=(n, rank))
    K = A @ A.T
    d = np.sqrt(np.diag(K))
    return K / np.outer(d, d)  # unit diagonal -> trace n


# --- normalisation ------------------------------------------------------------

def test_normalise_sets_trace_to_n():
    K = random_psd_kernel(8, seed=1) * 7.3
    Kn = normalise_kernel(K)
    assert np.isclose(np.trace(Kn), 8)


def test_normalise_rejects_non_positive_trace():
    with pytest.raises(ValueError):
        normalise_kernel(np.zeros((4, 4)))


# --- identity: g(K||K) == 1 ---------------------------------------------------

@pytest.mark.parametrize("n", [4, 8, 16])
def test_identical_kernels_give_g_one(n):
    """If the quantum kernel IS the classical kernel, there is no separation."""
    K = random_psd_kernel(n, seed=n)
    assert np.isclose(geometric_difference(K, K), 1.0, atol=1e-6)


@pytest.mark.parametrize("n", [4, 8, 16])
def test_identical_kernels_give_g_one_regularised(n):
    K = random_psd_kernel(n, seed=n)
    g = geometric_difference_regularised(K, K, lam=1e-10)
    assert np.isclose(g, 1.0, atol=1e-4)


# --- scale invariance ---------------------------------------------------------

def test_g_is_scale_invariant_when_normalising():
    K_c = random_psd_kernel(10, seed=2)
    K_q = random_psd_kernel(10, seed=3)
    g1 = geometric_difference(K_c, K_q)
    g2 = geometric_difference(K_c * 13.0, K_q * 0.02)
    assert np.isclose(g1, g2, rtol=1e-8)


# --- the ceiling: g <= sqrt(n), attained by a maximally-separated pair --------

@pytest.mark.parametrize("n", [4, 9, 16])
def test_orthogonal_classical_vs_rank_one_quantum_attains_ceiling(n):
    """K_C = I (classical sees every point as orthogonal) and K_Q = all-ones
    (quantum collapses them) is the maximally separated pair: g == sqrt(n)."""
    K_c = np.eye(n)
    K_q = np.ones((n, n))
    g = geometric_difference(K_c, K_q)
    assert np.isclose(g, np.sqrt(n), rtol=1e-6)


@pytest.mark.parametrize("seed", range(8))
def test_g_never_below_one(seed):
    """g < 1 would mean the quantum kernel is strictly dominated, which the
    definition does not permit. This bound does hold unconditionally."""
    n = 12
    K_c = random_psd_kernel(n, seed=seed)
    K_q = random_psd_kernel(n, seed=seed + 100)
    with pytest.warns(RuntimeWarning):  # under-regularised on purpose
        g = geometric_difference_regularised(K_c, K_q, lam=1e-8)
    assert g >= 1.0 - 1e-6


@pytest.mark.parametrize("seed", range(8))
def test_a_lambda_exists_that_brings_g_under_the_ceiling(seed):
    """The sqrt(n) ceiling is NOT unconditional in lam -- it holds only once lam
    is large enough for the conditioning of K_C. Measured on 12x12 random pairs:
    lam=1e-8 gives g up to 72 (ceiling 3.46), crossing under the ceiling around
    lam ~ 0.01-0.04. This pins that such a lam exists and the sweep finds it."""
    n = 12
    K_c = random_psd_kernel(n, seed=seed)
    K_q = random_psd_kernel(n, seed=seed + 100)
    sweep = g_lambda_sweep(K_c, K_q)
    assert sweep["n_lambdas_below_ceiling"] > 0, f"no lam in the sweep is interpretable: {sweep}"


@pytest.mark.parametrize("seed", range(4))
def test_regularised_g_falls_below_one_under_heavy_regularisation(seed):
    """g_lam < 1 is reachable and is an ARTEFACT of regularising only the
    classical side -- it does not mean the quantum kernel is dominated. The
    g >= 1 bound belongs to the unregularised metric alone. Documented here so
    nobody 'fixes' this by clamping g at 1, which would hide the artefact."""
    n = 12
    K_c = random_psd_kernel(n, seed=seed)
    K_q = random_psd_kernel(n, seed=seed + 100)
    g_heavy = geometric_difference_regularised(K_c, K_q, lam=10.0, warn_above_ceiling=False)
    assert g_heavy < 1.0


def test_g_is_not_comparable_across_different_lambdas():
    """Why the protocol fixes lam across every cell in a reported figure: the
    same kernel pair's g moves by more than an order of magnitude across the
    plausible lam range, which swamps any real between-cell difference."""
    n = 12
    K_c = random_psd_kernel(n, seed=0)
    K_q = random_psd_kernel(n, seed=100)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        g_small = geometric_difference_regularised(K_c, K_q, lam=1e-2)
        g_large = geometric_difference_regularised(K_c, K_q, lam=1.0)
    assert g_small / g_large > 5.0, (
        f"same kernel pair, different lam: g={g_small:.3f} vs {g_large:.3f}. "
        "If this ratio ever shrinks below 5 the metric became lam-insensitive "
        "and the fixed-lam protocol can be relaxed."
    )


def test_under_regularised_g_warns_instead_of_returning_silently():
    """The failure mode that would have corrupted the headline figure: a huge g
    from an ill-conditioned classical kernel, mistaken for quantum separation."""
    n = 12
    K_c = random_psd_kernel(n, seed=0)
    K_q = random_psd_kernel(n, seed=100)
    with pytest.warns(RuntimeWarning, match="under-regularised"):
        geometric_difference_regularised(K_c, K_q, lam=1e-10)


def test_g_tracks_classical_kernel_conditioning_not_just_separation():
    """Documents the measured pathology: with lam fixed and small, g rises with
    cond(K_C). If this ever stops being true the instability was fixed upstream
    and the lam protocol can be revisited."""
    n = 12
    K_q = random_psd_kernel(n, seed=100)
    pairs = []
    for seed in range(5):
        K_c = random_psd_kernel(n, seed=seed)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            g = geometric_difference_regularised(K_c, K_q, lam=1e-8)
        pairs.append((np.linalg.cond(normalise_kernel(K_c)), g))
    conds, gs = zip(*sorted(pairs))
    assert gs[-1] > gs[0], f"expected g to rise with cond(K_C), got {pairs}"


def test_lambda_from_svm_C_is_monotone_and_positive():
    n = 100
    assert lambda_from_svm_C(1.0, n) > lambda_from_svm_C(10.0, n) > 0
    with pytest.raises(ValueError):
        lambda_from_svm_C(0.0, n)


def test_lambda_from_svm_C_is_one_over_2C_and_does_not_scale_with_n():
    """D14's decision of 4 October 2026, pinned.

    The rule is lam = 1/(2C), from Appendix D's summed objective. The factor of
    n that the first version carried came from a docstring claim that cited
    nothing and is withdrawn. An unpinned definition is how that version
    survived unexamined for the whole of the registered sweep, so the exact
    value is asserted here, not just its monotonicity.
    """
    assert lambda_from_svm_C(1.0, 100) == 0.5
    assert lambda_from_svm_C(10.0, 350) == 0.05
    assert lambda_from_svm_C(1e-4, 200) == 5000.0
    # n must not move the answer. This is the whole content of the correction.
    vals = {lambda_from_svm_C(32.0, n) for n in (1, 50, 100, 200, 350, 10_000)}
    assert len(vals) == 1, f"lam varies with n: {sorted(vals)}"
    assert vals.pop() == 1.0 / 64.0


def test_lambda_from_svm_C_rejects_nonpositive_n():
    """n is unused but still validated: a caller passing 0 or a negative n has a
    bug, and silently ignoring it would hide the bug rather than the parameter.
    """
    for bad in (0, -1):
        with pytest.raises(ValueError):
            lambda_from_svm_C(1.0, bad)


def test_g_lambda_sweep_reports_ceiling_and_conditioning():
    n = 12
    K_c = random_psd_kernel(n, seed=0)
    K_q = random_psd_kernel(n, seed=100)
    out = g_lambda_sweep(K_c, K_q)
    assert out["n"] == n
    assert np.isclose(out["ceiling_sqrt_n"], np.sqrt(n))
    assert out["cond_K_classical"] > 1.0
    gs = list(out["g_by_lambda"].values())
    assert gs == sorted(gs, reverse=True), "g must shrink as lam grows"


# --- regularised converges to unregularised as lam -> 0 -----------------------

def test_regularised_converges_to_unregularised():
    """This is the check that the two implementations are the same formula."""
    K_c = random_psd_kernel(10, seed=4)
    K_q = random_psd_kernel(10, seed=5)
    g_exact = geometric_difference(K_c, K_q)
    errors = [
        abs(geometric_difference_regularised(K_c, K_q, lam=lam) - g_exact)
        for lam in (1e-4, 1e-6, 1e-8, 1e-10)
    ]
    assert errors == sorted(errors, reverse=True), f"not monotone: {errors}"
    assert errors[-1] < 1e-4


def test_larger_lambda_gives_smaller_or_equal_g():
    """More classical regularisation -> a more conservative estimate of room
    for quantum advantage. Guards against a sign/inversion error."""
    K_c = random_psd_kernel(10, seed=6)
    K_q = random_psd_kernel(10, seed=7)
    gs = [geometric_difference_regularised(K_c, K_q, lam=lam) for lam in (1e-10, 1e-6, 1e-3, 1e-1)]
    assert gs == sorted(gs, reverse=True), f"g should shrink as lam grows: {gs}"


# --- guards -------------------------------------------------------------------

def test_shape_mismatch_raises():
    with pytest.raises(ValueError):
        geometric_difference(np.eye(4), np.eye(5))


def test_non_square_raises():
    with pytest.raises(ValueError):
        geometric_difference(np.ones((3, 4)), np.ones((3, 4)))


def test_interpret_g_rules_out_advantage_for_identical_kernels():
    K = random_psd_kernel(64, seed=8)
    msg = interpret_g(geometric_difference(K, K), 64)
    assert "RULED OUT" in msg


# ------------------------------------------- F20, the training diagnostic
#
# Added 6 October 2026 for D16. g_tra selects lambda under Huang's own rule, and
# the rule is the only lambda procedure his source prints. Neither this project
# nor Florez Ablan et al. ever compared a g_tra to anything, so this function has
# no prior art inside either codebase to check against: the properties below are
# the check.


def test_g_tra_matches_the_closed_form_when_the_kernels_coincide():
    """For K_C == K_Q the quadratic form has eigenvalues mu/(mu+lam)^2, so

        g_tra = lam * max_i sqrt(mu_i) / (mu_i + lam)

    THE MAXIMUM IS NOT AT mu_max. mu/(mu+lam)^2 peaks at mu = lam, so the
    maximising eigenvalue is whichever lies nearest lam. The first version of
    this test asserted the mu_max form and failed by a factor of 18 at
    lam = 1e-5, which is how the error was found: the implementation was right
    and the asserted closed form was wrong.
    """
    n = 10
    K = random_psd_kernel(n, seed=3)
    mus = np.linalg.eigvalsh(normalise_kernel(K))
    for lam in (1e-5, 1e-3, 1e-2, 0.045, 0.1, 1.0):
        want = float(np.max(lam * np.sqrt(mus) / (mus + lam)))
        got = geometric_difference_training(K, K, lam=lam)
        assert got == pytest.approx(want, rel=1e-9), (lam, got, want)
        # The peak of mu/(mu+lam)^2 is 1/(4 lam), so this bound is tight-ish and
        # holds for every spectrum. It is D5's cap, seen from F20.
        assert got <= np.sqrt(lam) / 2 + 1e-12, (lam, got)


def test_g_tra_cannot_exceed_the_quantum_kernels_spectral_norm():
    """|| (K_C + lam I)^-2 || <= 1/lam^2, so g_tra <= sqrt(|| K_Q ||), which on
    trace-normalised matrices is at most sqrt(N). Worth pinning because it says
    how demanding Huang's 0.045 threshold is: the quantity has room to be orders
    of magnitude above it."""
    K_c = random_psd_kernel(10, seed=41)
    K_q = random_psd_kernel(10, seed=42)
    cap = float(np.sqrt(np.linalg.eigvalsh(normalise_kernel(K_q)).max()))
    for lam in (1e-5, 1e-3, 1e-1, 1.0):
        assert geometric_difference_training(K_c, K_q, lam=lam) <= cap + 1e-9


def test_g_tra_is_non_decreasing_in_lambda():
    """The theorem D16 section 10 relies on for the selection to be well posed:
    lam^2 (K_C+lam I)^-2 rises in the Loewner order, so g_tra cannot fall as lam
    rises, so the admissible set is a down-set and 'largest admissible lam' means
    something. If this ever fails, the grid search in D16 is not well defined."""
    lams = (1e-5, 1e-4, 1e-3, 1e-2, 0.025, 0.05, 0.1)
    for seed in range(6):
        K_c = random_psd_kernel(12, seed=seed)
        K_q = random_psd_kernel(12, seed=seed + 50)
        gs = [geometric_difference_training(K_c, K_q, lam=l) for l in lams]
        assert all(b >= a - 1e-12 for a, b in zip(gs, gs[1:])), (seed, gs)


def test_g_tra_pulls_against_the_ceiling_constraint():
    """The two constraints move opposite ways, which is why lambda selection is
    not free: g_tra <= 0.045 bounds lambda from above, the sqrt(n) ceiling on
    g_gen bounds it from below."""
    K_c = random_psd_kernel(12, seed=11)
    K_q = random_psd_kernel(12, seed=77)
    lo, hi = 1e-4, 1e-1
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        g_lo = geometric_difference_regularised(K_c, K_q, lam=lo)
        g_hi = geometric_difference_regularised(K_c, K_q, lam=hi)
    assert g_lo >= g_hi                                        # g_gen falls with lam
    assert (geometric_difference_training(K_c, K_q, lam=lo)
            <= geometric_difference_training(K_c, K_q, lam=hi))  # g_tra rises


def test_g_tra_is_zero_at_zero_lambda_and_never_negative():
    K_c = random_psd_kernel(8, seed=5)
    K_q = random_psd_kernel(8, seed=6)
    assert geometric_difference_training(K_c, K_q, lam=0.0) == 0.0
    for lam in (1e-6, 1e-3, 1.0):
        assert geometric_difference_training(K_c, K_q, lam=lam) >= 0.0


def test_g_tra_inverts_the_classical_kernel_not_the_quantum_one():
    """Orientation, pinned by an exact value rather than by an inequality.

    D16 section 2 fixes K2 = K_C: the matrix inverted in F20 is the one inverted
    in F19, which for `geometric_difference_regularised(K_C, K_Q, ...)` is K_C.

    THE FIRST VERSION OF THIS TEST WAS VACUOUS. It asserted only that swapping
    the arguments changes the answer, which is true of the correct function AND
    of a mutant that inverts K_Q instead. That mutant passed all 51 tests in this
    file. It was caught by running the mutation rather than by reading the test
    name, which is the whole argument for scripts/mutation_check.py.

    Set K_Q = I, so sqrt(K_Q) = I and the correct answer collapses to

        g_tra = lam * || (K_C + lam I)^-1 ||  =  lam / (mu_min(K_C) + lam)

    governed by the SMALLEST eigenvalue of K_C. The mutant that inverts K_Q
    instead gives lam * sqrt(mu_max(K_C)) / (1 + lam), governed by the LARGEST.
    A diagonal K_C with a small and a large eigenvalue separates them by a factor
    of about six.
    """
    n = 4
    d = np.array([0.01, 0.01, 1.0, 2.98])        # trace 4.0, so already normalised
    K_c = np.diag(d)
    K_q = np.eye(n)
    lam = 0.1

    want = lam / (d.min() + lam)                  # 0.9090..., inverting K_C
    wrong = lam * np.sqrt(d.max()) / (1.0 + lam)  # 0.1569..., inverting K_Q

    got = geometric_difference_training(K_c, K_q, lam=lam)
    assert got == pytest.approx(want, rel=1e-9), (got, want)
    assert got != pytest.approx(wrong, rel=1e-3), "the wrong matrix is inverted"

    # And the reverse call really does land on the other value, which confirms
    # the two orientations are distinguishable by this fixture rather than
    # coincidentally equal.
    assert (geometric_difference_training(K_q, K_c, lam=lam)
            == pytest.approx(wrong, rel=1e-9))


def test_g_tra_normalises_like_its_companion():
    """Both functions trace-normalise by default, so a rescaled pair must give
    the same answer. Huang's g is defined on tr(K) = N matrices."""
    K_c = random_psd_kernel(9, seed=31)
    K_q = random_psd_kernel(9, seed=32)
    a = geometric_difference_training(K_c, K_q, lam=1e-2)
    b = geometric_difference_training(17.0 * K_c, 0.3 * K_q, lam=1e-2)
    assert a == pytest.approx(b, rel=1e-9)
