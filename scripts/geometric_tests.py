#!/usr/bin/env python3
"""H2 and H3, exactly as section 6 of the pre-registration writes them.

WHY THIS RUNS FIVE WEEKS LATE
------------------------------
The pre-registration registers three confirmatory hypotheses and says of the
second: "H2 is the reason this project exists." H1 was tested in week 4. H2 and
H3 never were. The project turned toward the audit protocol and did not come
back, and two of three registered confirmatory tests have been sitting
unexecuted since.

WHAT IS REGISTERED, AND IS NOT NEGOTIABLE HERE
-----------------------------------------------
Section 6, verbatim in substance:

  H2: Spearman rank correlation between g_lambda and the observed mean paired
      difference in normAP, across all 360 units (2 datasets x 3 mappings x 5
      qubit counts x 3 training sizes x 4 quantum settings). Two-sided, alpha
      0.05, single test. Reported within each dataset separately as a
      pre-declared secondary.

  H3: Units split at g_lambda = 2. Compare the distribution of |observed
      difference| above and below the split by Mann-Whitney U, two-sided,
      alpha 0.05. The threshold is fixed and not tuned afterwards.

D5 (in force) freezes the lambda sweep at (1e-1, 1e-2, 1e-3, 1e-4) plus
lambda-from-C, requires the conclusion to hold at every lambda where no unit
breaches its sqrt(n) ceiling, and requires breach counts to be reported rather
than silently dropped.

D7 (in force) fixes what section 6 leaves silent: g is computed per seed
against that seed's own inner-CV-selected classical kernel; a unit's g is the
MEDIAN across seeds, not the mean; the IQR is reported; seeds breaching their
ceiling are excluded at that lambda; a unit with fewer than 10 surviving seeds
at a lambda is excluded there and reported as excluded. The per-seed version is
a declared sensitivity check and never the confirmatory one.

D8 (declared here, before any sweep output exists) fixes three further things
section 6 and D7 are both silent on, because writing the test stage forced them:

  (a) A unit's g is a median over the seeds that survive the ceiling rule at
      that lambda. The observed difference it is paired with is the mean over
      THE SAME surviving seeds, not over all twenty. Pairing a median computed
      on one seed set against a mean computed on another correlates two
      quantities measured on different data.
  (b) H2's correlation is also computed on the subset of units whose |observed
      difference| exceeds the precision floor (1e-3 in AP), and the
      confirmatory verdict requires that subset to agree in sign and also
      reject. A rank correlation across units whose differences all sit below
      the resolution of the comparison that produced them is a correlation
      among noise, and week 4 established that most of this project's observed
      differences are near that floor.
  (c) H3 as registered compares |observed difference| above and below the
      split, which cannot distinguish "quantum much better" from "quantum much
      worse". It is executed exactly as registered. The signed version is
      reported alongside as a secondary, pre-declared here rather than chosen
      after seeing which one is favourable.

THE CONTROLS, BECAUSE NOTHING HERE GETS BELIEVED WITHOUT ONE
-------------------------------------------------------------
Week 6 found eight defects in this project's analysis code, none caught by a
test and all caught by a control with a known answer. So:

  A. The fast path must equal `geometric_difference_regularised` exactly. This
     script reuses sqrt(K_C) and the per-lambda solve across the four quantum
     settings that share a classical kernel -- a 4x saving on the expensive
     half -- and that optimisation is worth nothing if it changes the number.
  B. g(K, K) must equal mu_max / (mu_max + lambda), where mu_max is the largest
     eigenvalue of the normalised kernel. NOT 1. With K_Q = K_C = K the
     regularised expression collapses to ||K (K + lam I)^-2 K||_inf, whose
     eigenvalues are mu^2/(mu+lam)^2, so the identical-kernel value approaches
     1 only as lambda -> 0. This control was first written expecting exactly 1
     and failed at 1.24e-02; the expectation was wrong, not the code. It is
     worth stating plainly that "g near 1 rules advantage out" therefore has a
     lambda-dependent floor BELOW 1, and comparing g to 1 at large lambda is
     biased.
  C. An angle kernel at small bandwidth against its fitted RBF must give g near
     1, because week 6 established those are the same kernel to four
     significant figures. This is the control that uses real data.

  D. A monotone synthetic table must give Spearman rho exactly +1.
  E. The D7 median must resist one wild seed where the mean does not: ten seeds
     at g = 1.0 and one at 15.0 give median 1.0 and mean 2.27. This is the
     specific behaviour D7 chose the median FOR, so it is checked rather than
     assumed.
  F. The ceiling rule and the 10-seed minimum must exclude and COUNT, never
     silently drop: a unit with nine survivors leaves the table and appears in
     the excluded list.
  G. Mann-Whitney must reproduce an exact known value: three-against-three with
     complete separation gives U = 9 and two-sided p = 0.1 exactly.

If any control fails the script refuses to report H2 or H3.

Usage:
    PYTHONPATH=src python scripts/geometric_tests.py --controls-only
    PYTHONPATH=src python scripts/geometric_tests.py --datasets churn \
        --out results/audits/g_units.jsonl
    PYTHONPATH=src python scripts/geometric_tests.py --test \
        --units results/audits/g_units.jsonl
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from qbench.data import balanced_subsample, load_dataset, make_split  # noqa: E402
from qbench.features import fit_mapping, scale_to_angles  # noqa: E402
from qbench.kernels.classical import build_classical_kernel  # noqa: E402
from qbench.kernels.geometric_difference import (  # noqa: E402
    _matrix_sqrt_psd, _spectral_norm_sym, geometric_difference_regularised,
    lambda_from_svm_C, normalise_kernel)
from qbench.kernels.quantum import QuantumGramFactory  # noqa: E402
from primary_tests import best_by_inner, load, norm_ap  # noqa: E402
from qbench.stats import rank_correlation  # noqa: E402

LAMBDAS = (1e-1, 1e-2, 1e-3, 1e-4)          # D5, frozen. from-C added per seed.
G_SPLIT = 2.0                                # H3 threshold, registered.
ALPHA = 0.05
MIN_SEEDS = 10                               # D7
SETTINGS = ("angle-r1", "angle-r2", "iqp-r1", "iqp-r2")
MAPPINGS = ("pca", "selectk", "randproj")
QUBITS = (4, 6, 8, 10, 12)
SIZES = (250, 100, 50)


# --------------------------------------------------------------- the fast path

def g_for_settings(K_c, K_qs, lams):
    """g for several quantum kernels against ONE classical kernel.

    Identical arithmetic to `geometric_difference_regularised`, with the two
    classical-side steps hoisted out of the loop because K_C does not change
    across the four settings in a cell. Control A proves the equality.
    """
    K_c = normalise_kernel(np.asarray(K_c, dtype=float))
    n = K_c.shape[0]
    sqrt_Kc = _matrix_sqrt_psd(K_c)
    core = {}
    for lam in lams:
        inner = np.linalg.solve(K_c + lam * np.eye(n), sqrt_Kc)
        core[lam] = inner @ inner.T
    out = {}
    for name, K_q in K_qs.items():
        sq = _matrix_sqrt_psd(normalise_kernel(np.asarray(K_q, dtype=float)))
        out[name] = {lam: float(np.sqrt(max(
            _spectral_norm_sym(sq @ core[lam] @ sq), 0.0))) for lam in lams}
    return out, float(np.sqrt(n))


# ------------------------------------------------------------------- controls

def controls(verbose=True):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(40, 5))
    sq = np.sum((X[:, None, :] - X[None, :, :]) ** 2, axis=-1)
    K_c = np.exp(-0.3 * sq)
    K_q = np.exp(-0.9 * sq)
    lams = (1e-1, 1e-3)
    ok = {}

    fast, _ = g_for_settings(K_c, {"q": K_q}, lams)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        ref = {lam: geometric_difference_regularised(K_c, K_q, lam=lam)
               for lam in lams}
    worst = max(abs(fast["q"][l] - ref[l]) for l in lams)
    ok["A fast path == module"] = (worst < 1e-9, f"max |diff| {worst:.2e}")

    # Analytic: with K_Q = K_C = K, g = mu_max / (mu_max + lam).
    probe = tuple(lams) + (1e-8,)
    same, _ = g_for_settings(K_c, {"same": K_c}, probe)
    mu = float(np.linalg.eigvalsh(normalise_kernel(K_c)).max())
    off = max(abs(same["same"][l] - mu / (mu + l)) for l in probe)
    ok["B g(K,K) == mu/(mu+lam)"] = (
        off < 1e-9,
        f"max |g - mu/(mu+lam)| {off:.2e}; mu_max {mu:.3f}, "
        f"g at lam=1e-1 is {same['same'][1e-1]:.4f}, at 1e-8 is "
        f"{same['same'][1e-8]:.6f}")

    # C: an angle kernel at small bandwidth IS its fitted RBF (week 6, to 4 s.f.)
    Xa = rng.uniform(-np.pi, np.pi, size=(40, 4))
    f = QuantumGramFactory(4)
    K_angle = f.gram_fn({"embedding": "angle", "reps": 1, "bandwidth": 0.02})(Xa)
    sqa = np.sum((Xa[:, None, :] - Xa[None, :, :]) ** 2, axis=-1)
    K_rbf = np.exp(-0.25 * 0.02 ** 2 * sqa)          # gamma = (reps*b)^2/4
    gc, _ = g_for_settings(K_rbf, {"angle": K_angle}, (1e-1,))
    v = gc["angle"][1e-1]
    ok["C g(RBF, angle@b=0.02) ~ 1"] = (abs(v - 1.0) < 0.05, f"g = {v:.4f}")

    # I: the registered arm's params carry NO bandwidth key. The sweep now
    # builds every quantum Gram from the record's own params, so nothing is
    # assumed -- but the hardcoded bandwidth=1.0 it replaced has to be shown to
    # have been right where it applied, otherwise every g in an earlier run of
    # this script would have been for a kernel the experiment never used. These
    # must be bit-identical, and if the factory's default ever moves off 1.0
    # this is what catches it.
    bare = f.gram_fn({"embedding": "angle", "reps": 1})(Xa)
    one = f.gram_fn({"embedding": "angle", "reps": 1, "bandwidth": 1.0})(Xa)
    worst_b = float(np.max(np.abs(np.asarray(bare) - np.asarray(one))))
    ok["I record params == bandwidth 1.0"] = (
        worst_b == 0.0,
        f"max |diff| {worst_b:.2e} (registered params carry no bandwidth key)")

    if verbose:
        for k, (passed, detail) in ok.items():
            print(f"  [{'PASS' if passed else 'FAIL'}] {k:<32} {detail}")
    return all(p for p, _ in ok.values())


# ------------------------------------------------------------------ the sweep

def cell_seeds(dataset, n_per_class, mapping, nq, seed, q_by, c_by, arm):
    """g for one (cell, seed): four settings against that seed's best classical."""
    key = (mapping, nq, seed)
    crecs = c_by.get(key, [])
    qrecs = {r["setting"]: r for r in q_by.get(key, [])}
    if not crecs or len(qrecs) < len(SETTINGS):
        return None
    best_c = best_by_inner(crecs)

    X, y, _ = load_dataset(dataset)
    Xs, ys = balanced_subsample(X, y, n_per_class=n_per_class, seed=seed)
    X_tr, _, y_tr, _ = make_split(Xs, ys, seed=seed)
    Xm, _ = fit_mapping(X_tr, y_tr, nq, mapping, seed=seed)
    Xa, _ = scale_to_angles(Xm)
    Xa = np.asarray(Xa, dtype=float)

    K_c = build_classical_kernel(best_c["method"], **(best_c.get("params") or {}))(Xa)
    lam_c = lambda_from_svm_C(float(best_c["C"]), Xa.shape[0])
    lams = tuple(LAMBDAS) + (lam_c,)

    # Built from the RECORD'S OWN params, never from a hardcoded bandwidth.
    # The first version of this function passed bandwidth=1.0 for every setting.
    # That happens to be right for the registered arm, whose params carry no
    # bandwidth key at all, but it is right by coincidence rather than by
    # construction, and it is flatly wrong for the bandwidth arm, where the
    # selected bandwidth varies by seed between 0.0625 and 1.0. A g computed for
    # a kernel the experiment never ran is the same defect class as every other
    # one this project has found: the analysis substituting its own parameter
    # for the measurement's. Control I proves the two paths agree where both
    # apply.
    fac = QuantumGramFactory(nq)
    K_qs = {s: fac.gram_fn(dict(qrecs[s]["params"]))(Xa) for s in SETTINGS}
    gs, ceiling = g_for_settings(K_c, K_qs, lams)
    fac.clear()

    c_nap = norm_ap(best_c)
    return [{"dataset": dataset, "n_per_class": n_per_class, "mapping": mapping,
             "n_qubits": nq, "setting": s, "seed": seed, "arm": arm,
             "quantum_params": dict(qrecs[s]["params"]),
             "quantum_bandwidth": float(qrecs[s]["params"].get("bandwidth", 1.0)),
             "classical_method": best_c["method"], "classical_C": float(best_c["C"]),
             "lambda_from_C": lam_c, "ceiling": ceiling,
             "g": {f"{l:g}": gs[s][l] for l in lams},
             "g_from_C": gs[s][lam_c],
             "d_normap": norm_ap(qrecs[s]) - c_nap} for s in SETTINGS]


def index(recs, extra=()):
    out = {}
    for r in recs:
        out.setdefault((r["mapping"], int(r["n_qubits"]), int(r["seed"])), []).append(r)
    return out


def sweep(datasets, sizes, out_path, q_dir, c_dir, limit=None, arm="registered",
          mappings=MAPPINGS, qubits=QUBITS):
    """One arm per output file, never mixed.

    `arm` is part of the resume key AND of every row. Without it a resumed run
    against a different arm would find the (dataset, size, cell, seed) key
    already present and skip silently, leaving a file that looks complete and
    holds two arms' g under one label. That is the filename-collision failure
    this project already had once, one level deeper.
    """
    done = set()
    p = Path(out_path)
    if p.exists():
        seen_arms = set()
        for line in p.read_text().splitlines():
            r = json.loads(line)
            seen_arms.add(r.get("arm", "registered"))
            done.add((r.get("arm", "registered"), r["dataset"], r["n_per_class"],
                      r["mapping"], r["n_qubits"], r["seed"]))
        if seen_arms - {arm}:
            raise SystemExit(
                f"\n  {p} already holds arm(s) {sorted(seen_arms)} and this run "
                f"is arm '{arm}'.\n  One arm per file. Write this run somewhere "
                f"else rather than mixing them.")
        print(f"  resuming: {len(done)} (cell, seed) combinations already done")
    p.parent.mkdir(parents=True, exist_ok=True)
    suffix = "_bw" if arm == "bandwidth" else ""
    t0, n = time.perf_counter(), 0
    for dataset, npc in itertools.product(datasets, sizes):
        qf = Path(q_dir) / f"{dataset}_matched_n{npc}{suffix}.jsonl"
        cf = Path(c_dir) / f"{dataset}_matched_n{npc}.jsonl"
        # primary_tests.load takes a Path and returns None for a missing file;
        # audit.load takes a str. Passing str here raised AttributeError on the
        # first line of the first real sweep, after three commits had described
        # this analysis as fixed in advance of its data. None is checked
        # explicitly rather than trusted, because a loader that returns None
        # instead of raising turns a missing file into a silent skip.
        q, c = load(qf), load(cf)
        if not q or not c:
            missing = [f.name for f, v in ((qf, q), (cf, c)) if not v]
            print(f"  skipping {dataset} n={npc} [{arm}]: missing or empty "
                  f"{', '.join(missing)}")
            continue
        q_by, c_by = index(q), index(c)
        seeds = sorted({int(r["seed"]) for r in q})
        for mapping, nq, seed in itertools.product(mappings, qubits, seeds):
            if (arm, dataset, npc, mapping, nq, seed) in done:
                continue
            rows = cell_seeds(dataset, npc, mapping, nq, seed, q_by, c_by, arm)
            if rows is None:
                continue
            with p.open("a") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
            n += 1
            if n % 25 == 0:
                el = time.perf_counter() - t0
                print(f"  {n} cells, {el/60:.1f} min, {el/n:.1f} s/cell")
            if limit and n >= limit:
                el = time.perf_counter() - t0
                print(f"  stopped at --limit {limit}: {n} cells in {el:.1f} s, "
                      f"{el/max(n,1):.1f} s/cell")
                print(f"  These were whatever the loop reached first: "
                      f"the loop runs mapping-major, so a small --limit samples "
                      f"only\n  the lowest qubit count. Cost rises steeply with "
                      f"qubits, so do NOT multiply\n  this figure by the full "
                      f"cell count. Use --qubits to time the expensive end.")
                return
    el = time.perf_counter() - t0
    print(f"  {n} new (cell, seed) combinations in {el/60:.1f} min"
          + (f", {el/n:.1f} s/cell" if n else ""))


# ------------------------------------------------ aggregation (D7 and D8a)

LAM_COLS = tuple(f"{l:g}" for l in LAMBDAS) + ("from_C",)
UNIT_FIELDS = ("dataset", "n_per_class", "mapping", "n_qubits", "setting")
REGISTERED_UNITS = 360
MIN_UNITS = 12                    # below this the rank test is not estimable
FLOOR = 1e-3                      # D2's precision floor, in AP


def g_at(row, col):
    """g at one lambda column. from_C lives in its own field because the
    per-seed lambda differs by seed, so it cannot share a dict key."""
    return float(row["g_from_C"]) if col == "from_C" else float(row["g"][col])


def units_at(rows, col):
    """Per-seed rows -> units at one lambda, by D7 and D8(a).

    Ceiling breaches are excluded and counted. A unit with fewer than MIN_SEEDS
    survivors leaves the table and is named in `excluded`. The unit's g is the
    median over survivors and its observed difference is the mean over THE SAME
    survivors.
    """
    by = {}
    for r in rows:
        by.setdefault(tuple(r[f] for f in UNIT_FIELDS), []).append(r)
    units, excluded, breaches, total = [], [], 0, 0
    for key, rs in sorted(by.items(), key=str):
        kept = []
        for r in rs:
            g = g_at(r, col)
            total += 1
            if g > float(r["ceiling"]):
                breaches += 1
            else:
                kept.append((g, float(r["d_normap"])))
        base = dict(zip(UNIT_FIELDS, key))
        if len(kept) < MIN_SEEDS:
            excluded.append({**base, "surviving_seeds": len(kept),
                             "of_seeds": len(rs), "reason": "below MIN_SEEDS"})
            continue
        gs = np.array([g for g, _ in kept])
        ds = np.array([d for _, d in kept])
        q1, q3 = np.percentile(gs, [25, 75])
        units.append({**base, "g": float(np.median(gs)), "g_iqr": float(q3 - q1),
                      "d": float(ds.mean()), "seeds": len(kept)})
    # `total` is returned with `breaches` and never without it. A bare breach
    # count is how docs/deviations.md D5 came to publish "9/8": the source log
    # printed 9 with no denominator, the transcription supplied "/8" from the
    # seed count, and the real denominator was 16 because the counter pooled two
    # bandwidth columns. An impossible fraction sat in a published record for
    # four days. A count printed without what it is a count OF is a defect.
    return units, excluded, breaches, total


# ------------------------------------------------------------- the two tests

def fmt_p(p):
    """A p-value that underflows to zero is a display artefact, not a result.

    The first version of this stage printed `p 0.00e+00` for the per-seed
    sensitivity, which reads as a certainty no finite sample can supply. This is
    the same defect class as tekeli_check.py printing `+/- 0.000` for a standard
    error it had not actually resolved.
    """
    return "<1e-300" if p == 0.0 else f"{p:.2e}"


def spearman_ci(rho, n, alpha=ALPHA):
    """Fisher-z interval. Not in section 6; the project's own verdict rule
    requires an interval that excludes zero, so one is computed and labelled.

    rho is clamped to 1 - 1/(2n) before the z transform. Without the clamp a
    perfect rank correlation gives arctanh(1) = inf, the interval comes back
    None, `ci_excludes_zero` is then False, and the verdict rule reports the
    STRONGEST possible result as NOT SUPPORTED. Control D covers this.
    """
    if n < 5 or not np.isfinite(rho):
        return None, None
    cap = 1.0 - 1.0 / (2.0 * n)
    z = np.arctanh(np.clip(rho, -cap, cap))
    se = 1.0 / np.sqrt(n - 3)
    crit = stats.norm.ppf(1 - alpha / 2)
    return float(np.tanh(z - crit * se)), float(np.tanh(z + crit * se))


def h2(units, label="all units"):
    """Spearman(g, observed difference), two-sided, as section 6 registers."""
    if len(units) < MIN_UNITS:
        return {"label": label, "n_units": len(units), "estimable": False,
                "why": f"{len(units)} units, fewer than {MIN_UNITS}"}
    g = [u["g"] for u in units]
    d = [u["d"] for u in units]
    rc = rank_correlation(g, d)
    rho, p = (rc.rho, rc.p) if rc.ok else (None, None)
    if not rc.ok:
        # A constant input makes Spearman undefined and scipy returns NaN with a
        # ConstantInputWarning. Without this guard `rejects` is bool(nan < 0.05)
        # = False and the verdict reads NOT SUPPORTED -- a substantive answer --
        # where the truth is that no correlation exists to test. Found by
        # tests/test_geometric_tests.py on its first run.
        return {"label": label, "n_units": len(units), "estimable": False,
                "why": rc.why,
                "constant_g": bool(len(set(g)) == 1),
                "constant_d": bool(len(set(d)) == 1)}
    lo, hi = spearman_ci(rho, len(units))
    resolved = [u for u in units if abs(u["d"]) > FLOOR]
    sub = None
    if len(resolved) >= MIN_UNITS:                       # D8(b)
        rc2 = rank_correlation([u["g"] for u in resolved],
                               [u["d"] for u in resolved])
        r2, p2 = (rc2.rho, rc2.p) if rc2.ok else (float("nan"), float("nan"))
        # Same NaN guard as above: the subset can be constant even when the
        # full set is not, and a NaN rho here would make the D8(b) agreement
        # check silently pass by comparing nan * rho > 0, which is False.
        sub = ({"n_units": len(resolved), "rho": float(r2), "p": float(p2),
                "rejects": bool(p2 < ALPHA)} if np.isfinite(r2) else
               {"n_units": len(resolved), "rho": None, "p": None,
                "rejects": False, "why": "constant input; rho undefined"})
    return {"label": label, "n_units": len(units), "estimable": True,
            "rho": float(rho), "p": float(p), "ci": [lo, hi],
            "rejects": bool(p < ALPHA),
            "ci_excludes_zero": bool(lo is not None and lo * hi > 0),
            "n_above_floor": len(resolved), "resolved_subset": sub}


def _median_diff_ci(a, b, reps=10000, seed=0, alpha=ALPHA):
    """Percentile bootstrap on median(a) - median(b). Fixed seed: this number
    goes into a verdict, so it must be identical on every re-run."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a), np.asarray(b)
    draws = np.array([np.median(rng.choice(a, a.size, replace=True))
                      - np.median(rng.choice(b, b.size, replace=True))
                      for _ in range(reps)])
    lo, hi = np.percentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def h3(units, label="all units"):
    """Mann-Whitney U on |observed difference| above vs below g = 2, as
    registered, with the signed version as D8(c)'s pre-declared secondary."""
    above = [u for u in units if u["g"] > G_SPLIT]
    below = [u for u in units if u["g"] <= G_SPLIT]
    out = {"label": label, "n_above": len(above), "n_below": len(below),
           "split": G_SPLIT, "n_units": len(units)}
    if len(units) < MIN_UNITS:
        # Same floor as H2. Without this, eight units gave H3 a verdict of NOT
        # SUPPORTED on a 5-versus-3 comparison while H2 on the identical eight
        # correctly refused. Two different answers about the same data is not a
        # finding, it is an inconsistent guard.
        out.update(estimable=False,
                   why=f"{len(units)} units, fewer than {MIN_UNITS}")
        return out
    if min(len(above), len(below)) < 3:
        out.update(estimable=False,
                   why=f"{len(above)} above and {len(below)} below the split; "
                       f"a fixed threshold that stops partitioning the data has "
                       f"stopped being a test")
        return out
    aa = [abs(u["d"]) for u in above]
    bb = [abs(u["d"]) for u in below]
    U, p = stats.mannwhitneyu(aa, bb, alternative="two-sided")
    eff = float(np.median(aa) - np.median(bb))
    lo, hi = _median_diff_ci(aa, bb)
    sa, sp = stats.mannwhitneyu([u["d"] for u in above], [u["d"] for u in below],
                                alternative="two-sided")
    out.update(estimable=True, U=float(U), p=float(p),
               median_above=float(np.median(aa)), median_below=float(np.median(bb)),
               median_diff=eff, ci=[lo, hi],
               rank_biserial=float(2 * U / (len(aa) * len(bb)) - 1),
               rejects=bool(p < ALPHA),
               ci_excludes_zero=bool(lo * hi > 0),
               exceeds_floor=bool(abs(eff) > FLOOR),
               signed_secondary={"U": float(sa), "p": float(sp),
                                 "median_above": float(np.median([u["d"] for u in above])),
                                 "median_below": float(np.median([u["d"] for u in below]))})
    return out


def verdict(res, keys):
    """The project's three-condition rule, stated in one place."""
    if not res.get("estimable"):
        return "NOT ESTIMABLE"
    return "SUPPORTED" if all(res.get(k) for k in keys) else "NOT SUPPORTED"


# ------------------------------------------------------- controls for --test

def test_controls(verbose=True):
    ok = {}

    def unit(ds, mp, nq, st, gs, ds_, ceil=100.0):
        return [{"dataset": ds, "n_per_class": 250, "mapping": mp, "n_qubits": nq,
                 "setting": st, "seed": i, "ceiling": ceil,
                 "g": {"0.1": g}, "g_from_C": g, "d_normap": d}
                for i, (g, d) in enumerate(zip(gs, ds_))]

    # D: a monotone table must give rho exactly +1.
    rows = []
    for i in range(MIN_UNITS + 4):
        rows += unit("synth", "pca", 4 + i, f"s{i}", [1.0 + i] * 12,
                     [0.01 * (i + 1)] * 12)
    u, ex, br, tot = units_at(rows, "0.1")
    r = h2(u)
    v = verdict(r, ("rejects", "ci_excludes_zero"))
    ok["D monotone -> rho == +1, SUPPORTED"] = (
        abs(r["rho"] - 1.0) < 1e-12 and len(u) == MIN_UNITS + 4 and not ex
        and v == "SUPPORTED",
        f"rho {r['rho']:+.12f} over {len(u)} units, CI "
        f"[{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}], {v}")

    # E: the median must resist one wild seed where the mean does not.
    gs = [1.0] * 10 + [15.0]
    rows = unit("synth", "pca", 4, "s", gs, [0.0] * 11, ceil=18.71)
    u, _, br, tot = units_at(rows, "0.1")
    ok["E median resists one wild seed"] = (
        len(u) == 1 and abs(u[0]["g"] - 1.0) < 1e-12 and br == 0,
        f"median {u[0]['g']:.4f} vs mean {np.mean(gs):.4f}, "
        f"{br} breaches (all 11 under the 18.71 ceiling)")

    # F: ceiling breach and the 10-seed minimum must exclude AND count.
    rows = unit("synth", "pca", 4, "s", [1.0] * 9 + [99.0, 99.0], [0.0] * 11,
                ceil=18.71)
    u, ex, br, tot = units_at(rows, "0.1")
    ok["F ceiling + MIN_SEEDS exclude and count"] = (
        u == [] and len(ex) == 1 and ex[0]["surviving_seeds"] == 9 and br == 2,
        f"{len(u)} units kept, 1 excluded at {ex[0]['surviving_seeds']}/11 "
        f"survivors, {br}/{tot} breaches (denominator always printed)")

    # G: Mann-Whitney against an exact hand value: 3v3 separated, U=9, p=0.1.
    U, p = stats.mannwhitneyu([4, 5, 6], [1, 2, 3], alternative="two-sided")
    ok["G Mann-Whitney 3v3 -> U=9, p=0.1"] = (
        abs(U - 9) < 1e-12 and abs(p - 0.1) < 1e-12, f"U {U:.0f}, p {p:.6f}")

    # H: the negative control. g uncorrelated with the difference must give NOT
    # SUPPORTED on both tests. A stage that finds a result in noise is worse
    # than one that finds nothing, and every defect week 6 turned up was a
    # detector substituting its own behaviour for the measurement.
    r2 = np.random.default_rng(11)
    rows = []
    for i in range(60):
        base = 1.0 + 4.0 * r2.random()
        rows += unit("synth", "pca", 4 + i % 5, f"s{i}",
                     [base + r2.normal(0, 0.15) for _ in range(20)],
                     [float(r2.normal(0, 0.003)) for _ in range(20)])
    u, _, _, _ = units_at(rows, "0.1")
    n2, n3 = h2(u), h3(u)
    v2 = verdict(n2, ("rejects", "ci_excludes_zero"))
    v3 = verdict(n3, ("rejects", "ci_excludes_zero", "exceeds_floor"))
    ok["H no signal -> NOT SUPPORTED on both"] = (
        v2 == "NOT SUPPORTED" and v3 == "NOT SUPPORTED",
        f"H2 rho {n2['rho']:+.4f} p {n2['p']:.3f} -> {v2}; "
        f"H3 p {n3['p']:.3f} -> {v3}")

    if verbose:
        for k, (passed, detail) in ok.items():
            print(f"  [{'PASS' if passed else 'FAIL'}] {k:<38} {detail}")
    return all(p for p, _ in ok.values())


# ------------------------------------------------------------ the test stage

def run_tests(units_path, json_out=None):
    rows = [json.loads(l) for l in Path(units_path).read_text().splitlines() if l]
    print(f"\n  {len(rows)} per-seed rows from {units_path}")
    for ds in sorted({r["dataset"] for r in rows}):
        n = len({(r["mapping"], r["n_qubits"], r["setting"], r["n_per_class"])
                 for r in rows if r["dataset"] == ds})
        print(f"    {ds}: {n} distinct units present")

    report = {"units_file": str(units_path), "lambda_columns": list(LAM_COLS),
              "registered_units": REGISTERED_UNITS, "by_lambda": {}}
    print(f"\n  H2 -- Spearman(g, observed difference), two-sided, alpha {ALPHA}")
    print(f"  {'lambda':>8} {'units':>7} {'breach':>11} {'excl':>5} "
          f"{'rho':>8} {'p':>9} {'95% CI':>18} {'>floor':>7} {'verdict':>14}")
    for col in LAM_COLS:
        u, ex, br, tot = units_at(rows, col)
        r = h2(u)
        v = verdict(r, ("rejects", "ci_excludes_zero"))
        if v == "SUPPORTED" and r.get("resolved_subset"):      # D8(b)
            s = r["resolved_subset"]
            if s["rho"] is None or not (s["rejects"]
                                        and s["rho"] * r["rho"] > 0):
                v = "NOT SUPPORTED"
        ci = ("-" if not r.get("ci") or r["ci"][0] is None
              else f"[{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}]")
        body = (f"{r['rho']:+.4f} {fmt_p(r['p']):>9} {ci:>18} "
                f"{r['n_above_floor']:7d}" if r.get("estimable")
                else f"{'-':>8} {'-':>9} {'-':>18} {'-':>7}")
        print(f"  {col:>8} {len(u):7d} {f'{br}/{tot}':>11} {len(ex):5d} "
              f"{body} {v:>14}")
        report["by_lambda"][col] = {"h2": r, "excluded": ex, "breaches": br,
                                   "breach_denominator": tot,
                                   "h2_verdict": v, "n_units": len(u)}

    print(f"\n  H3 -- Mann-Whitney U on |difference| above vs below g = {G_SPLIT}")
    print(f"  {'lambda':>8} {'above':>6} {'below':>6} {'med above':>10} "
          f"{'med below':>10} {'p':>9} {'signed p':>9} {'verdict':>14}")
    for col in LAM_COLS:
        u, _, _, _ = units_at(rows, col)
        r = h3(u)
        v = verdict(r, ("rejects", "ci_excludes_zero", "exceeds_floor"))
        body = (f"{r['median_above']:10.4f} {r['median_below']:10.4f} "
                f"{fmt_p(r['p']):>9} {fmt_p(r['signed_secondary']['p']):>9}"
                if r.get("estimable")
                else f"{'-':>10} {'-':>10} {'-':>9} {'-':>9}")
        print(f"  {col:>8} {r['n_above']:6d} {r['n_below']:6d} {body} {v:>14}")
        report["by_lambda"][col]["h3"] = r
        report["by_lambda"][col]["h3_verdict"] = v

    # D5: the conclusion must hold at every lambda with no ceiling breach.
    clean = [c for c in LAM_COLS if report["by_lambda"][c]["breaches"] == 0]
    print(f"\n  D5: {len(clean)} of {len(LAM_COLS)} lambda columns have zero "
          f"ceiling breaches" + (f" ({', '.join(clean)})" if clean else ""))
    for name, key in (("H2", "h2_verdict"), ("H3", "h3_verdict")):
        vs = {report["by_lambda"][c][key] for c in clean} if clean else set()
        if not clean:
            out = "NOT ESTABLISHED (no breach-free lambda)"
        elif len(vs) == 1:
            out = f"{vs.pop()} at every breach-free lambda"
        else:
            out = "NOT SUPPORTED (verdict differs across breach-free lambdas)"
        print(f"    {name} confirmatory: {out}")
        report[f"{name.lower()}_confirmatory"] = out

    # Per-seed sensitivity: declared in D7, never confirmatory.
    print(f"\n  Sensitivity (D7): per-seed rows, not units. NOT confirmatory.")
    report["per_seed_sensitivity"] = {}
    for col in LAM_COLS:
        pairs = [(g_at(r, col), float(r["d_normap"])) for r in rows
                 if g_at(r, col) <= float(r["ceiling"])]
        if len(pairs) < MIN_UNITS:
            continue
        # The third call site in this file. The NaN guard went into the other
        # two and not this one, which is the same partial fix rbf_surrogate made
        # when it guarded q and d but not g.
        rcs = rank_correlation([a for a, _ in pairs], [b for _, b in pairs])
        if not rcs.ok:
            print(f"    lambda {col:>7}: {len(pairs):5d} rows, not estimable "
                  f"({rcs.why})")
            report["per_seed_sensitivity"][col] = {"n_rows": len(pairs),
                                                  "rho": None, "p": None,
                                                  "why": rcs.why}
            continue
        print(f"    lambda {col:>7}: {len(pairs):5d} rows, rho {rcs.rho:+.4f}, "
              f"p {fmt_p(rcs.p)}")
        report["per_seed_sensitivity"][col] = {"n_rows": len(pairs),
                                              "rho": rcs.rho, "p": rcs.p}

    # A too-small arm gets a listing, not a silence. The bandwidth arm covers one
    # cell per dataset -- 4 units each, 8 in all -- which is below MIN_UNITS, so
    # H2 there is genuinely not estimable (D9). Printing the units is what makes
    # it useful anyway: if the sign of the g-to-difference relation differs in
    # the one cell where the bandwidth confound is removed, that is a limitation
    # on H2's headline result and it should be readable rather than inferred.
    first = report["by_lambda"][LAM_COLS[0]]
    if 0 < first["n_units"] < MIN_UNITS:
        print(f"\n  Fewer than {MIN_UNITS} units, so neither test is estimable. "
              f"The units themselves:")
        print(f"  {'dataset':>8} {'n':>4} {'mapping':>9} {'q':>3} {'setting':>9} "
              f"{'bw':>7} {'seeds':>6} " + " ".join(f"{'g@'+c:>10}" for c in LAM_COLS)
              + f" {'mean d':>9}")
        bws = {}
        for r in rows:
            bws.setdefault(tuple(r[f] for f in UNIT_FIELDS), []).append(
                float(r.get("quantum_bandwidth", 1.0)))
        per_lam = {c: {tuple(u[f] for f in UNIT_FIELDS): u
                       for u in units_at(rows, c)[0]} for c in LAM_COLS}
        for u in units_at(rows, LAM_COLS[0])[0]:
            k = tuple(u[f] for f in UNIT_FIELDS)
            b = bws.get(k, [1.0])
            gtxt = " ".join(
                (f"{per_lam[c][k]['g']:10.4f}" if k in per_lam[c] else f"{'-':>10}")
                for c in LAM_COLS)
            print(f"  {u['dataset']:>8} {u['n_per_class']:4d} {u['mapping']:>9} "
                  f"{u['n_qubits']:3d} {u['setting']:>9} "
                  f"{np.median(b):7.4f} {u['seeds']:6d} {gtxt} {u['d']:+9.4f}")
        print("  Descriptive only. Not a test, and not to be quoted as one.")

    n_present = len({tuple(r[f] for f in UNIT_FIELDS) for r in rows})
    arms = sorted({r.get("arm", "registered") for r in rows})
    report["arms"] = arms
    if arms == ["registered"]:
        print(f"\n  {n_present} of {REGISTERED_UNITS} registered units are "
              f"present in this file.")
        if n_present < REGISTERED_UNITS:
            print(f"  The sweep is incomplete. Every number above is computed on "
                  f"what is\n  present and is not the registered test until it "
                  f"is {REGISTERED_UNITS}.")
    else:
        # The bandwidth arm's universe is one cell per dataset, not 360, so
        # quoting 8 of 360 would read as a 98% shortfall rather than a complete
        # arm that is simply too small to test (D9).
        print(f"\n  arm(s) {arms}: {n_present} units. This is NOT the registered "
              f"universe of {REGISTERED_UNITS};\n  the bandwidth arm covers one "
              f"cell per dataset by design and cannot support H2.")
    if json_out:
        p = Path(json_out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, indent=2, default=float) + "\n")
        print(f"\n-> {p}")


def check_inputs(datasets, sizes, q_dir, c_dir, arm):
    """Resolve and load every input file BEFORE any g is computed.

    Not a control -- it has no known answer -- but a precondition. The nine
    controls all exercise arithmetic; none of them opens a results file, which
    is why a str-versus-Path error in `sweep` survived three commits and only
    appeared on the first line of the first real run. This reads record counts
    and nothing else: no Gram matrix, no g, no metric.
    """
    suffix = "_bw" if arm == "bandwidth" else ""
    ok, rows = True, []
    for dataset, npc in itertools.product(datasets, sizes):
        qf = Path(q_dir) / f"{dataset}_matched_n{npc}{suffix}.jsonl"
        cf = Path(c_dir) / f"{dataset}_matched_n{npc}.jsonl"
        for f, side in ((qf, "quantum"), (cf, "classical")):
            recs = load(f)
            if not recs:
                rows.append((f.name, side, "MISSING OR EMPTY", "", ""))
                ok = False
                continue
            sets = sorted({r.get("setting") or r.get("method") for r in recs})
            seeds = len({r["seed"] for r in recs})
            rows.append((f.name, side, f"{len(recs)} recs",
                         f"{seeds} seeds", f"{len(sets)} settings/methods"))
    w = max(len(r[0]) for r in rows) if rows else 10
    for name, side, a1, a2, a3 in rows:
        print(f"  {name:<{w}}  {side:<9} {a1:>16} {a2:>9} {a3:>20}")
    return ok


def build_parser():
    """The CLI, as a value rather than a side effect.

    Extracted from main() so a test can inspect the option strings directly.
    The previous test scraped --help output and asserted `"--test" in text`,
    which stayed true when the flag was renamed to --test-GONE because the help
    string for --units reads "sweep output to test (with --test)". The
    assertion was satisfied by prose in another argument's help text, and the
    mutation survived twice: once on the substring, once on the word boundary.
    Text scraping cannot distinguish a flag that exists from a flag that is
    merely mentioned.
    """
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--controls-only", action="store_true")
    ap.add_argument("--test", action="store_true",
                    help="run H2 and H3 on an existing sweep file")
    ap.add_argument("--units", default="results/audits/g_units.jsonl",
                    help="sweep output to test (with --test)")
    ap.add_argument("--report", help="write the H2/H3 report JSON here")
    ap.add_argument("--datasets", nargs="*", default=["churn", "fraud"])
    ap.add_argument("--sizes", nargs="*", type=int, default=list(SIZES))
    ap.add_argument("--arm", choices=("registered", "bandwidth"),
                    default="registered",
                    help="registered: the pre-registered kernels. bandwidth: the "
                         "exploratory bandwidth-matched arm, which exists for one "
                         "cell per dataset and cannot support H2 (see D9).")
    ap.add_argument("--out", help="sweep output; defaults per arm so the two "
                                  "cannot share a file")
    ap.add_argument("--limit", type=int, help="stop after N cells (smoke test)")
    ap.add_argument("--mappings", nargs="*", default=list(MAPPINGS),
                    help="restrict the sweep to these mappings")
    ap.add_argument("--qubits", nargs="*", type=int, default=list(QUBITS),
                    help="restrict the sweep to these qubit counts. Use this to "
                         "time the EXPENSIVE end: a small --limit otherwise "
                         "samples only the cheapest cells, because the loop runs "
                         "mapping-major and reaches 12 qubits only after 80 cells.")
    ap.add_argument("--quantum-dir", default=str(ROOT / "results" / "runs" / "quantum"))
    ap.add_argument("--classical-dir", default=str(ROOT / "results" / "runs" / "classical"))
    return ap


def main():
    args = build_parser().parse_args()
    if not args.out:
        args.out = ("results/audits/g_units.jsonl" if args.arm == "registered"
                    else "results/audits/g_units_bw.jsonl")

    print("\nH2 and H3: g against observed difference, as section 6 registers them.")
    print("D5 freezes the lambda sweep; D7 fixes the seed aggregation.\n")
    print("Controls on g:")
    if not controls():
        raise SystemExit("\n  A control failed. Nothing computed below it would "
                         "be interpretable; fix the control first.")
    print("\nControls on the aggregation and the two tests:")
    if not test_controls():
        raise SystemExit("\n  A control failed. Nothing computed below it would "
                         "be interpretable; fix the control first.")
    if args.controls_only:
        return
    if args.test:
        if not Path(args.units).exists():
            raise SystemExit(f"\n  {args.units} does not exist. Run the sweep "
                             f"first; --test reads its output and computes "
                             f"nothing itself.")
        run_tests(args.units, args.report)
        return
    print()
    print(f"\nInput check, arm: {args.arm} (no g computed here):")
    if not check_inputs(args.datasets, args.sizes, args.quantum_dir,
                        args.classical_dir, args.arm):
        raise SystemExit("\n  An input file is missing or empty. Fix that before "
                         "the sweep;\n  a sweep that silently skips a file "
                         "produces a table that looks complete.")
    print()
    sweep(args.datasets, args.sizes, args.out,
          args.quantum_dir, args.classical_dir, args.limit, args.arm,
          tuple(args.mappings), tuple(args.qubits))
    print(f"\n-> {args.out}\n  Run with --test once the sweep is complete.")


if __name__ == "__main__":
    main()
