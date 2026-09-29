"""Rank correlation that refuses rather than returning NaN.

WHY THIS MODULE EXISTS
----------------------
`scipy.stats.spearmanr` returns NaN with a `ConstantInputWarning` when either
input is constant. NaN then propagates silently through every comparison,
because every comparison against NaN is False:

    nan <= 0     -> False      so a "warn if not positive" branch never fires
    nan < 0.05   -> False      so a "rejects" flag reads as no rejection
    nan * r > 0  -> False      so an agreement check silently disagrees

Each of those turns an UNDEFINED correlation into a definite verdict, and in
every case the verdict is the reassuring one. This project found the pattern in
`geometric_tests.h2`, where a constant observed difference produced NOT
SUPPORTED instead of NOT ESTIMABLE, and then found the same unguarded call in
seven more places. Three of them had been emitting `ConstantInputWarning` on
every `make test` run for weeks.

The scattered fix -- an `isfinite` check at each call site -- is what produced
the problem in the first place: `rbf_surrogate` guards two of its three inputs
and `geometric_tests` was fixed at two of its three call sites, in both cases by
someone who believed they had covered it.

So the refusal is moved into one place and the caller cannot get a number
without also getting the flag that says whether the number means anything.

WHAT IT DOES NOT DO
-------------------
It does not decide what a caller should report when the correlation is
undefined. An audit check should SKIP or WARN, a test stage should say NOT
ESTIMABLE, a diagnostic can print "n/a". Those are different and the caller
chooses. This only guarantees that `ok` is False whenever `rho` is not a usable
number, so the choice cannot be skipped by accident.
"""

from __future__ import annotations

import warnings
from typing import NamedTuple, Sequence

import numpy as np
from scipy import stats


class RankCorr(NamedTuple):
    """A rank correlation, or a refusal with the reason attached.

    `ok` is False whenever `rho` is unusable. `rho` and `p` are then None
    rather than NaN, so a caller that ignores `ok` gets a TypeError on the next
    arithmetic operation instead of a silently False comparison.
    """
    rho: float | None
    p: float | None
    ok: bool
    why: str
    n: int

    def __bool__(self) -> bool:      # `if rc:` reads as "is this usable"
        return self.ok


def rank_correlation(x: Sequence[float], y: Sequence[float],
                     *, min_n: int = 3) -> RankCorr:
    """Spearman rho, or a refusal naming which input made it undefined."""
    a = np.asarray(list(x), dtype=float)
    b = np.asarray(list(y), dtype=float)
    n = int(a.size)

    if b.size != n:
        return RankCorr(None, None, False,
                        f"length mismatch: {n} against {b.size}", n)
    if n < min_n:
        return RankCorr(None, None, False,
                        f"{n} points, fewer than {min_n}", n)
    if not (np.all(np.isfinite(a)) and np.all(np.isfinite(b))):
        return RankCorr(None, None, False,
                        "input contains NaN or infinity", n)

    const_a, const_b = len(np.unique(a)) == 1, len(np.unique(b)) == 1
    if const_a or const_b:
        which = ("both inputs are" if const_a and const_b
                 else "the first input is" if const_a
                 else "the second input is")
        return RankCorr(None, None, False,
                        f"{which} constant, so the rank correlation is "
                        f"undefined. This is not a null result.", n)

    with warnings.catch_warnings():
        # Anything left that scipy warns about is a defect in the guards above,
        # so it is raised rather than printed past.
        warnings.simplefilter("error", stats.ConstantInputWarning)
        rho, p = stats.spearmanr(a, b)

    if not (np.isfinite(rho) and np.isfinite(p)):
        return RankCorr(None, None, False,
                        "scipy returned a non-finite value on input the guards "
                        "above accepted, which is a defect in those guards", n)
    return RankCorr(float(rho), float(p), True, "", n)


def fmt_rho(rc: RankCorr, width: int = 8) -> str:
    """A rank correlation formatted for a table, refusals included."""
    return f"{rc.rho:+.4f}".rjust(width) if rc.ok else "n/a".rjust(width)


def fmt_p(p: float | None) -> str:
    """A p-value that underflows to zero is a display artefact, not a result.

    Printing `0.00e+00` reads as a certainty no finite sample supplies. Same
    defect class as a standard error rendered at `.3f` when it is 1e-7.
    """
    if p is None:
        return "n/a"
    return "<1e-300" if p == 0.0 else f"{p:.2e}"
