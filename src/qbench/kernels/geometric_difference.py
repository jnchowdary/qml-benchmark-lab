"""Geometric difference g(K_C || K_Q), after Huang et al. 2021.

Reference
---------
Huang, H.-Y., Broughton, M., Mohseni, M., Babbush, R., Boixo, S., Neven, H.,
McClean, J. R. "Power of data in quantum machine learning."
Nature Communications 12, 2631 (2021). arXiv:2011.01938

What it is
----------
Given two kernel (Gram) matrices over the SAME n data points -- K_C from a
classical kernel, K_Q from a quantum kernel -- the geometric difference

    g(K_C || K_Q) = sqrt( || sqrt(K_Q) K_C^{-1} sqrt(K_Q) ||_inf )

bounds how much better the quantum model could possibly be than the classical
one, over the worst-case labelling consistent with the data.

How to read it
--------------
  g ~ 1          -> the classical kernel can reproduce whatever the quantum
                    kernel does. A quantum advantage is RULED OUT on this data.
  g ~ sqrt(n)    -> there EXISTS some labelling for which the quantum kernel
                    separates what the classical one cannot.

This is a NECESSARY, NOT SUFFICIENT condition. A large g does not predict that
the quantum kernel wins on *your* labels -- only that it is not excluded. The
whole point of this project is to test empirically whether g predicts the
observed performance gap on real business tabular data, so treat g as the
independent variable under test, never as a result in itself.

Both kernels MUST be trace-normalised to n before comparison (see
`normalise_kernel`); g is not scale-invariant and comparing an unnormalised
pair silently produces a meaningless number.

A WARNING, MEASURED NOT ASSUMED
-------------------------------
g is NOT a stable single number. Measured here on random 12x12 kernel pairs, g
at lam=1e-8 ranged from 9.1 to 72.1 against a nominal ceiling of sqrt(12)=3.46,
and the value tracked cond(K_C) almost perfectly (cond 3.2e2 -> g 9.1;
cond 2.1e4 -> g 72.1). Computed carelessly, g measures how ill-conditioned your
classical kernel is, not how different the quantum kernel is. A
g-versus-performance scatter built on unregularised g is a plot of numerical
noise wearing a physics costume.

The protocol this project follows as a result:
  1. Always use `geometric_difference_regularised` with an explicit lam.
  2. Tie lam to the classical model actually being compared against, via
     `lambda_from_svm_C`. g then answers "can the trained classical SVM be
     beaten", which is the benchmark's question, rather than "could an
     infinitely flexible classical model be beaten", which it is not.
  3. Report `g_lambda_sweep` in the paper, not a single number. A g that moves
     by an order of magnitude across plausible lam is not a finding.
  4. g > sqrt(n) means under-regularised, not "large quantum separation".
     `geometric_difference_regularised` warns when this happens.
"""

from __future__ import annotations

import warnings

import numpy as np

__all__ = [
    "normalise_kernel",
    "geometric_difference",
    "geometric_difference_regularised",
    "lambda_from_svm_C",
    "g_lambda_sweep",
    "interpret_g",
]


def normalise_kernel(K: np.ndarray) -> np.ndarray:
    """Trace-normalise a Gram matrix so tr(K) == n.

    Huang et al. define g over kernels normalised this way. Fidelity kernels
    already have unit diagonal (so tr == n), but classical kernels generally do
    not, and RBF/poly kernels in particular will not.
    """
    K = np.asarray(K, dtype=float)
    n = K.shape[0]
    trace = np.trace(K)
    if trace <= 0:
        raise ValueError(f"Kernel has non-positive trace ({trace}); cannot normalise.")
    return K * (n / trace)


def _matrix_sqrt_psd(K: np.ndarray, floor: float = 0.0) -> np.ndarray:
    """Symmetric PSD square root via eigendecomposition.

    Uses eigh (not Cholesky) because fidelity kernel matrices from finite-shot
    or hardware runs routinely carry small negative eigenvalues from sampling
    noise, which makes Cholesky fail outright. Clipping at `floor` is the
    documented, inspectable way to handle that.
    """
    eigvals, eigvecs = np.linalg.eigh((K + K.T) / 2.0)
    eigvals = np.clip(eigvals, floor, None)
    return (eigvecs * np.sqrt(eigvals)) @ eigvecs.T


def _spectral_norm_sym(M: np.ndarray) -> float:
    return float(np.linalg.eigvalsh((M + M.T) / 2.0).max())


def geometric_difference(
    K_classical: np.ndarray,
    K_quantum: np.ndarray,
    *,
    normalise: bool = True,
    rcond: float = 1e-12,
) -> float:
    """Unregularised g(K_C || K_Q) = sqrt(|| sqrt(K_Q) K_C^-1 sqrt(K_Q) ||_inf).

    Provided for the lam -> 0 limit and for tests. DO NOT use this for reported
    results: on real data K_C is ill-conditioned and the result is dominated by
    that conditioning. Use `geometric_difference_regularised` instead.
    """
    K_c = np.asarray(K_classical, dtype=float)
    K_q = np.asarray(K_quantum, dtype=float)
    _check_pair(K_c, K_q)

    if normalise:
        K_c, K_q = normalise_kernel(K_c), normalise_kernel(K_q)

    sqrt_Kq = _matrix_sqrt_psd(K_q)
    K_c_inv = np.linalg.pinv(K_c, rcond=rcond, hermitian=True)
    return float(np.sqrt(max(_spectral_norm_sym(sqrt_Kq @ K_c_inv @ sqrt_Kq), 0.0)))


def geometric_difference_regularised(
    K_classical: np.ndarray,
    K_quantum: np.ndarray,
    *,
    lam: float = 1e-3,
    normalise: bool = True,
    warn_above_ceiling: bool = True,
) -> float:
    """Regularised g_lambda(K_C || K_Q). This is the one to use.

        g_lam = sqrt( || sqrt(K_Q) sqrt(K_C) (K_C + lam*I)^-2 sqrt(K_C) sqrt(K_Q) ||_inf )

    As lam -> 0 this converges to `geometric_difference`. Larger lam means a
    more heavily regularised classical model, i.e. a more conservative (smaller)
    estimate of the room available for quantum advantage.

    Report the lam you used alongside every g value. Different lam gives a
    different g, and a g quoted without its lam is not reproducible.

    Warns when g exceeds the sqrt(n) ceiling, which indicates lam is too small
    for this kernel's conditioning rather than a genuine large separation.
    """
    K_c = np.asarray(K_classical, dtype=float)
    K_q = np.asarray(K_quantum, dtype=float)
    _check_pair(K_c, K_q)

    if normalise:
        K_c, K_q = normalise_kernel(K_c), normalise_kernel(K_q)

    n = K_c.shape[0]
    sqrt_Kq = _matrix_sqrt_psd(K_q)
    sqrt_Kc = _matrix_sqrt_psd(K_c)

    inner = np.linalg.solve(K_c + lam * np.eye(n), sqrt_Kc)  # (K_c + lam I)^-1 sqrt(K_c)
    core = inner @ inner.T                                    # sqrt(Kc)(Kc+lam I)^-2 sqrt(Kc)
    g = float(np.sqrt(max(_spectral_norm_sym(sqrt_Kq @ core @ sqrt_Kq), 0.0)))

    if warn_above_ceiling and g > np.sqrt(n) * (1 + 1e-6):
        warnings.warn(
            f"g={g:.3f} exceeds the sqrt(n)={np.sqrt(n):.3f} ceiling at lam={lam:g} "
            f"(cond(K_C)={np.linalg.cond(K_c):.2e}). This means the classical kernel is "
            f"under-regularised, NOT that the quantum kernel separates strongly. "
            f"Raise lam (see lambda_from_svm_C) before reporting this value.",
            RuntimeWarning,
            stacklevel=2,
        )
    return g


def lambda_from_svm_C(C: float, n: int) -> float:
    """Map an SVM's C to the equivalent kernel-ridge regularisation lam.

    Normalising the SVC primal (1/2)||w||^2 + C * SUM_i loss_i so the per-sample
    loss carries coefficient 1 gives (1/(2C))||w||^2 + SUM_i loss_i, so the
    regulariser-to-loss ratio is

        lam = 1 / (2 * C)

    with no factor of n. This matches the summed objective Huang et al. use in
    Appendix D. The argument uses only the ratio of the two coefficients, so it
    establishes the regularisation SCALING only; it does not claim that an SVM's
    hinge loss and a kernel ridge's squared residual are otherwise equivalent.

    The previous version of this function returned 1/(2*C*n) on a docstring
    claim that cited nothing. That claim is withdrawn. See docs/deviations.md
    D14 and its decision record of 4 October 2026, which records the correction,
    the three callers it touches, and the outcome-to-verdict mapping fixed before
    any recomputed g was read.

    WARNING, and it is the important line here: Huang et al. do not derive lam
    from C at all. Their procedure is a g_tra grid search over a declared grid.
    This function is a SUBSTITUTE for that procedure, adopted by this project and
    independently by Florez Ablan et al., and neither group said so. It is not
    the source's method, and lam is still a function of a tuning outcome -- C is
    chosen by inner CV, so lam inherits that selection.

    `n` is retained in the signature and is deliberately unused. Every existing
    call site passes it; dropping the parameter would let a call written against
    the old rule keep working while silently meaning something else. It is
    validated and ignored.

    Use the C selected by the classical baseline's inner CV (section 7 of the
    plan), not a default, and record it beside every g in the results JSON.
    """
    if C <= 0:
        raise ValueError(f"C must be positive, got {C}")
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    return 1.0 / (2.0 * C)


def g_lambda_sweep(
    K_classical: np.ndarray,
    K_quantum: np.ndarray,
    lams=(1e-6, 1e-4, 1e-3, 1e-2, 1e-1, 1.0),
) -> dict:
    """g across a lam range, plus diagnostics. This is what the paper reports.

    Returns a dict with the sweep, the sqrt(n) ceiling, cond(K_C), and whether
    g is stable (varies by less than 2x across the middle of the range). An
    unstable g is a caveat to state, not a number to quote.
    """
    K_c = normalise_kernel(K_classical)
    K_q = normalise_kernel(K_quantum)
    n = K_c.shape[0]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        gs = {
            lam: geometric_difference_regularised(
                K_c, K_q, lam=lam, normalise=False, warn_above_ceiling=False
            )
            for lam in lams
        }
    below = [g for g in gs.values() if g <= np.sqrt(n)]
    stable = bool(below) and (max(below) / max(min(below), 1e-12) < 2.0)
    return {
        "g_by_lambda": gs,
        "ceiling_sqrt_n": float(np.sqrt(n)),
        "cond_K_classical": float(np.linalg.cond(K_c)),
        "n": n,
        "stable": stable,
        "n_lambdas_below_ceiling": len(below),
    }


def interpret_g(g: float, n: int) -> str:
    """Plain-language reading of a g value against its sqrt(n) ceiling.

    Deliberately conservative: never says "quantum advantage", only whether one
    is ruled out or merely not ruled out.
    """
    ceiling = np.sqrt(n)
    ratio = g / ceiling
    if ratio > 1.0:
        return (
            f"g={g:.3f} EXCEEDS ceiling sqrt(n)={ceiling:.3f}: under-regularised, "
            f"not interpretable. Raise lam."
        )
    if ratio < 0.15:
        verdict = "classical kernel reproduces the quantum one; advantage RULED OUT"
    elif ratio < 0.5:
        verdict = "limited separation; advantage unlikely but not excluded"
    else:
        verdict = "large separation; advantage NOT ruled out (not evidence of one)"
    return f"g={g:.3f} vs ceiling sqrt(n)={ceiling:.3f} (ratio {ratio:.2f}): {verdict}"


def _check_pair(K_c: np.ndarray, K_q: np.ndarray) -> None:
    if K_c.shape != K_q.shape:
        raise ValueError(f"Kernel shapes differ: {K_c.shape} vs {K_q.shape}")
    if K_c.ndim != 2 or K_c.shape[0] != K_c.shape[1]:
        raise ValueError(f"Kernels must be square 2-D matrices, got {K_c.shape}")
