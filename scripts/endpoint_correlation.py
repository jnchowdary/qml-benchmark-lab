#!/usr/bin/env python3
"""How much does demanding BOTH endpoints cost, measured rather than assumed?

THE DECISION THIS INFORMS
-------------------------
The pre-registration declares two primary endpoints: normalised average
precision and ROC-AUC. "Co-primary" has two standard meanings and they have
opposite statistical consequences.

  UNION (any endpoint may succeed)
      Needs alpha split across the endpoints. Measured cost: a uniform 12% on
      the minimum detectable effect, 0.0159 -> 0.0178 on churn's primary arm.

  INTERSECTION-UNION (every endpoint must succeed)
      Needs NO alpha adjustment: the type I error of "reject only if both
      reject" is at most the error of either test alone. But it loses power,
      because a true effect must clear the bar twice. How much it loses
      depends entirely on how correlated the two tests are, and that is an
      empirical question about this data.

Both endpoints are computed from the SAME decision scores on the SAME test
set, so they should be strongly correlated and the intersection-union rule
should be nearly free. "Should be" is not a measurement.

WHAT THIS MEASURES
------------------
1. The correlation between the per-seed paired difference in average precision
   and the per-seed paired difference in ROC-AUC, within each cell and kernel
   pair. These are exactly the paired differences week 9's tests will use.
2. The intersection-union minimum detectable effect at that correlation, by
   simulating the joint test, and the resulting cost against a single
   endpoint and against the union rule.

Assumption, stated because it is load-bearing: the simulation assumes a true
effect of the same STANDARDISED size on both endpoints. If a quantum kernel
improved ranking at the top without improving it overall, average precision
would move more than ROC-AUC and this would understate the cost. That is an
argument for reporting both endpoints whatever the rule, which the
pre-registration does.

Usage:
    PYTHONPATH=src python scripts/endpoint_correlation.py --all
    PYTHONPATH=src python scripts/endpoint_correlation.py --dataset churn --n-per-class 250
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from power_analysis import KERNELS, mde_paired_t  # noqa: E402

ALPHA = 0.05
POWER = 0.80
N_SIM = 40000


def paired_pairs(recs):
    """Per cell, per kernel pair: aligned (AP difference, ROC difference) by seed.

    Alignment is on the seed explicitly rather than on list order, because a
    silent misalignment between the two metrics would produce a correlation
    that means nothing and looks fine.
    """
    by_cell = defaultdict(dict)
    for r in recs:
        by_cell[(r["mapping"], r["n_qubits"], r["seed"])][r["method"]] = r

    out = defaultdict(lambda: defaultdict(list))
    for (mapping, nq, seed), by_method in by_cell.items():
        for i, a in enumerate(KERNELS):
            for b in KERNELS[i + 1:]:
                if a in by_method and b in by_method:
                    ra, rb = by_method[a], by_method[b]
                    out[(mapping, nq)][f"{a}-{b}"].append((
                        seed,
                        ra["test_average_precision"] - rb["test_average_precision"],
                        ra["test_roc_auc"] - rb["test_roc_auc"],
                    ))
    return out


def correlations(recs):
    rhos = []
    for by_pair in paired_pairs(recs).values():
        for rows in by_pair.values():
            if len(rows) < 4:
                continue
            rows = sorted(rows)                       # by seed
            ap = [r[1] for r in rows]
            roc = [r[2] for r in rows]
            if st.pstdev(ap) == 0 or st.pstdev(roc) == 0:
                continue
            rhos.append(float(np.corrcoef(ap, roc)[0, 1]))
    return rhos


def iu_mde(sd, n, rho, alpha=ALPHA, power=POWER, n_sim=N_SIM, seed=0):
    """Effect size at which BOTH one-sample t-tests reject with `power`.

    Simulated rather than solved, because the joint distribution of two
    correlated t statistics has no convenient closed form and an approximation
    here would be another unchecked assertion.
    """
    rng = np.random.default_rng(seed)
    crit = stats.t.ppf(1 - alpha / 2, n - 1)
    # Built as z2 = rho*z1 + sqrt(1-rho^2)*w rather than by Cholesky, which is
    # singular at rho = +-1. Perfect correlation is the case that matters most
    # here (it is the no-cost boundary), so the construction has to reach it.
    rho = float(np.clip(rho, -1.0, 1.0))
    tail = math.sqrt(max(1.0 - rho * rho, 0.0))

    def joint_power(delta):
        z1 = rng.standard_normal((n_sim, n))
        w = rng.standard_normal((n_sim, n))
        z2 = rho * z1 + tail * w
        z = np.stack([z1, z2], axis=2) + delta         # same standardised effect on both
        m = z.mean(axis=1)
        s = z.std(axis=1, ddof=1)
        t = m / (s / math.sqrt(n))
        return float(np.mean((t[:, 0] > crit) & (t[:, 1] > crit)))

    lo, hi = 0.0, 2.0
    while joint_power(hi) < power and hi < 50:
        hi *= 2
    for _ in range(40):
        mid = (lo + hi) / 2
        if joint_power(mid) < power:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2 * sd


def report(path, n_seeds=20):
    recs = [json.loads(line) for line in path.open()]
    rhos = correlations(recs)
    if not rhos:
        print(f"{path.name}: no usable pairs")
        return None

    sds = []
    for by_pair in paired_pairs(recs).values():
        for rows in by_pair.values():
            if len(rows) > 1:
                sds.append(st.stdev([r[1] for r in rows]))
    sd = float(np.median(sds))
    rho = float(np.median(rhos))

    single = mde_paired_t(sd, n_seeds, alpha=ALPHA)
    union = mde_paired_t(sd, n_seeds, alpha=ALPHA / 2)
    inter = iu_mde(sd, n_seeds, rho)

    print(f"\n=== {path.name} ===")
    print(f"    correlation of the AP and ROC-AUC paired differences, across {len(rhos)} "
          f"cell-pairs")
    print(f"      median {rho:+.3f}   IQR {np.percentile(rhos, 25):+.3f} to "
          f"{np.percentile(rhos, 75):+.3f}   min {min(rhos):+.3f}")
    print(f"    median paired sd (AP): {sd:.4f}")
    print(f"    MDE, single endpoint            : {single:.4f}")
    print(f"    MDE, union (alpha split)        : {union:.4f}   ({union / single - 1:+.0%})")
    print(f"    MDE, intersection-union         : {inter:.4f}   ({inter / single - 1:+.0%})")
    better = "intersection-union" if inter < union else "union"
    print(f"    cheaper rule here: {better}")
    return {"file": path.name, "n_cell_pairs": len(rhos), "rho_median": rho,
            "rho_iqr": [float(np.percentile(rhos, 25)), float(np.percentile(rhos, 75))],
            "rho_min": float(min(rhos)), "paired_sd": sd, "mde_single": single,
            "mde_union": union, "mde_intersection_union": inter}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset")
    ap.add_argument("--track", default="matched")
    ap.add_argument("--n-per-class", type=int)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--in-dir", default=str(ROOT / "results" / "runs" / "classical"))
    ap.add_argument("--out", default=str(ROOT / "results" / "analysis" / "endpoint_correlation.json"))
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    if args.all:
        paths = sorted(p for p in in_dir.glob("*.jsonl") if "_shuffled" not in p.name)
    else:
        if not args.dataset:
            ap.error("give --dataset or --all")
        tag = f"_n{args.n_per_class}" if args.n_per_class else ""
        paths = [in_dir / f"{args.dataset}_{args.track}{tag}.jsonl"]

    print("Two primary endpoints, same decision scores, same test set.")
    print("UNION needs alpha split; INTERSECTION-UNION needs no correction but must clear twice.")
    print(f"alpha={ALPHA}, power={POWER}, {N_SIM} simulations per step.")

    summaries = [s for s in (report(p) for p in paths if p.exists()) if s]
    for p in paths:
        if not p.exists():
            print(f"missing: {p.name}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"alpha": ALPHA, "power": POWER, "n_sim": N_SIM,
                               "summaries": summaries}, indent=2) + "\n")
    print(f"\n-> {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")


if __name__ == "__main__":
    main()
