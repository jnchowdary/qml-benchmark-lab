"""Chance-level average precision, computed exactly rather than assumed.

WHY THIS MODULE EXISTS
----------------------
On 23 Sep 2026 the label-shuffled negative control returned a mean PR-AUC of
0.0192 (churn) and 0.0223 (fraud) ABOVE the test base rate, at roughly 2.2 and
2.5 seed-level standard errors. The verdict block printed at the time said the
expectation was the base rate, so read literally it announced a leak in the
pipeline.

There is no leak. The claim "average precision of a random ranker equals the
base rate" is FALSE at finite sample size. Average precision is an average of
precision values taken at the rank of each positive, and precision at the top
of a random ranking is upward-biased because the first positive's rank is
small more often than the average would suggest. The bias shrinks as the
number of positives grows and is substantial when it is small:

    n_test = 30,  P = 15   ->  chance AP = 0.553   (base 0.500)
    n_test = 60,  P = 30   ->  chance AP = 0.531
    n_test = 150, P = 75   ->  chance AP = 0.516
    n_test = 600, P = 300  ->  chance AP = 0.506

Against those figures the control's residuals were +0.003, +0.006, -0.007 and
+0.005 with mixed signs, and ROC-AUC (which IS exactly 0.5 under the null)
came in at 0.5078, 0.5058, 0.4901 and 0.5031. The pipeline is clean.

WHAT THIS MEANS FOR THE PROJECT
-------------------------------
1. Paired comparisons are UNAFFECTED. Within one cell every method is scored
   on the same test set, so n and P are identical and the bias is a shared
   constant that cancels exactly in the difference. Every week-9 paired test,
   and every number scripts/power_analysis.py produces, is safe.

2. Comparisons ACROSS test-set sizes are affected, and the training-size sweep
   is exactly such a comparison. At 50 per class the chance floor is 0.553; at
   250 per class it is 0.516. A learning curve drawn on raw AP therefore
   understates its own slope by about 0.037, because the small-data arm is
   sitting on a higher floor. Churn's observed gap of 0.041 between those two
   arms is really closer to 0.078.

3. normAP must be normalised against the CHANCE level, not the base rate. The
   first version of that helper used the base rate and was optimistic, most so
   for the smallest test sets.

THE EXACT FORMULA
-----------------
For a uniformly random ranking of n items of which P are positive, sklearn's
step-wise average precision is (1/P) * sum_k k / R_k, where R_k is the rank of
the k-th positive. R_k is the k-th order statistic of a random P-subset of
{1..n}:

    P(R_k = r) = C(r-1, k-1) * C(n-r, P-k) / C(n, P)

so E[AP] = (1/P) * sum_k k * sum_r (1/r) * P(R_k = r), evaluated in log space.
This is exact, deterministic and needs no simulation. It is checked against
the analytic P=1 case (E[AP] = H_n / n) and against Monte Carlo in the tests,
because a formula I derived is not evidence until something independent agrees
with it -- which is the lesson that produced this module in the first place.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from scipy.special import gammaln

__all__ = ["chance_average_precision", "normalised_average_precision", "ap_chance_for_record"]


def _log_binom(n, k):
    """log C(n, k), vectorised, -inf outside the valid range."""
    n = np.asarray(n, dtype=float)
    k = np.asarray(k, dtype=float)
    ok = (k >= 0) & (k <= n) & (n >= 0)
    out = np.full(np.broadcast(n, k).shape, -np.inf)
    nn, kk = np.broadcast_arrays(n, k)
    out[ok] = (gammaln(nn[ok] + 1) - gammaln(kk[ok] + 1) - gammaln(nn[ok] - kk[ok] + 1))
    return out


@lru_cache(maxsize=4096)
def chance_average_precision(n: int, p: int) -> float:
    """Expected average precision of a uniformly random ranking.

    n is the number of test points, p the number of positives among them.
    Exact, not simulated. Returns the base rate p/n only in the limit; at
    finite n it is strictly larger whenever 0 < p < n.
    """
    n, p = int(n), int(p)
    if p <= 0 or n <= 0:
        raise ValueError(f"need 0 < p <= n, got n={n}, p={p}")
    if p >= n:
        return 1.0

    log_denom = float(_log_binom(n, p))
    r = np.arange(1, n + 1, dtype=float)
    total = 0.0
    for k in range(1, p + 1):
        log_pmf = _log_binom(r - 1, k - 1) + _log_binom(n - r, p - k) - log_denom
        total += k * float(np.sum(np.exp(log_pmf) / r))
    return total / p


def normalised_average_precision(ap: float, n: int, p: int) -> float:
    """(AP - chance) / (1 - chance): 0 is chance, 1 is a perfect ranking.

    Use this, never (AP - base)/(1 - base), for any comparison across
    different test-set sizes, base rates, datasets or tracks. Within a single
    cell it changes nothing, because chance is then a shared constant.
    """
    chance = chance_average_precision(n, p)
    return (ap - chance) / (1 - chance) if chance < 1 else float("nan")


def ap_chance_for_record(record) -> float:
    """Chance AP for one tuned record, from its stored test-set composition."""
    n = int(record["n_test"])
    p = int(round(record["test_base_rate"] * n))
    return chance_average_precision(n, p)
