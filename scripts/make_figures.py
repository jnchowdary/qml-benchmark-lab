#!/usr/bin/env python3
"""The three figures the results section needs.

`results/figures/` was empty until this script. Each figure is built from a
committed artefact and stamps its source into the figure itself, so a reader
can check any value against the file it came from.

FORM, chosen before colour
--------------------------
fig1  H2 across lambda. The job is polarity plus the evidence behind each
      point: rho reverses sign across the sweep, and the columns differ
      enormously in how many units survive. Two stacked panels on a shared log
      x-axis -- rho with 95% CI above, units retained below -- because a rho
      from 61 units with 299 excluded is not the same evidence as one from 360
      with none. Emphasis form: lambda = 0.1 is the only complete column and
      carries the accent; the rest are context in grey.

fig2  H1 paired differences. Two datasets on a SHARED x-scale, deliberately.
      Per-panel scales would let fraud's null fill a panel and invite a visual
      comparison against churn that the numbers do not support. On one scale
      fraud sits visibly at zero, which is the honest picture.

fig3  The churn exploratory families. Horizontal lollipop grouped by family.
      Emphasis again: Holm-significant levels in the accent, the rest grey.
      Only the significant levels are labelled -- a number on every point is
      clutter.

NO DUAL AXES anywhere. fig1's two panels share one x and have separate y for
separate quantities, which is small multiples, not a second y-scale on one plot.

COLOUR
------
Palette validated with the data-viz validator before use:
    #2a78d6, #eb6834 -> all six checks PASS on the light surface
    (CVD worst-adjacent dE 24.7 protan, normal-vision 33.6, contrast >= 3:1)
Text wears ink tokens, never the series colour.

Paper figures are static and light-surface only: no hover layer and no dark
mode, which the method requires for screen charts and which do not apply here.

Usage:
    PYTHONPATH=src python scripts/make_figures.py --check
    PYTHONPATH=src python scripts/make_figures.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import matplotlib                                              # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                # noqa: E402

from primary_tests import (CLASSICAL_KERNELS, CONFIRMATORY_N,  # noqa: E402
                           PRIMARY_CELL, integrity, load, paired_series)

OUT = ROOT / "results" / "figures"
H2 = ROOT / "results" / "audits" / "h2_h3_report.json"
EXPL = ROOT / "results" / "analysis" / "exploratory_sweep.json"
QDIR = ROOT / "results" / "runs" / "quantum"
CDIR = ROOT / "results" / "runs" / "classical"

# Validated light-surface tokens. Do not substitute by eye; re-run the
# validator if these change.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
ACCENT = "#2a78d6"
CONTEXT = "#898781"

LAM_ORDER = ["0.0001", "0.001", "0.01", "0.1", "from_C"]
LAM_X = {"0.0001": 1e-4, "0.001": 1e-3, "0.01": 1e-2, "0.1": 1e-1}


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(AXIS)
        ax.spines[s].set_linewidth(1.0)
    ax.tick_params(colors=MUTED, labelsize=8, length=3, width=1.0)
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_color(INK2)
    ax.grid(True, color=GRID, linewidth=0.8, alpha=1.0)
    ax.set_axisbelow(True)


def stamp(fig, text):
    # Placed BELOW the figure box (va="top" at negative y) so bbox_inches
    # "tight" expands to include it. At y>0 it lands on top of the x-axis
    # label, which is what the first render of figs 2 and 3 did.
    fig.text(0.0, -0.012, text, ha="left", va="top",
             fontsize=6.5, color=MUTED)


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext, kw in (("png", {"dpi": 200}), ("svg", {})):
        p = OUT / f"{name}.{ext}"
        fig.savefig(p, facecolor=SURFACE, bbox_inches="tight", **kw)
        print(f"  -> {p.relative_to(ROOT)}")
    plt.close(fig)


# ------------------------------------------------------------------ fig 1

def fig_h2_lambda():
    d = json.loads(H2.read_text())
    bl = d["by_lambda"]
    rows = []
    for k in LAM_ORDER:
        v = bl[k]
        h2 = v["h2"]
        rows.append({
            "key": k,
            "x": LAM_X.get(k),
            "rho": h2.get("rho"),
            "ci": h2.get("ci"),
            "units": h2.get("n_units"),
            "breaches": v.get("breaches"),
            "denom": v.get("breach_denominator"),
        })
    grid = [r for r in rows if r["x"] is not None]
    fromc = next(r for r in rows if r["key"] == "from_C")
    # from_C has no single lambda; it is placed to the right of the sweep and
    # separated by a rule so it is never read as part of the x scale.
    fromc["x"] = 10 ** (np.log10(1e-1) + 0.75)

    fig, (a1, a2) = plt.subplots(
        2, 1, figsize=(7.2, 5.4), sharex=True,
        gridspec_kw={"height_ratios": [2.0, 1.0], "hspace": 0.12})
    fig.patch.set_facecolor(SURFACE)

    for ax in (a1, a2):
        style(ax)
        ax.set_xscale("log")
        ax.axvline(10 ** (np.log10(1e-1) + 0.38), color=AXIS,
                   linewidth=1.0, linestyle=(0, (3, 3)), zorder=1)

    a1.axhline(0.0, color=AXIS, linewidth=1.2, zorder=2)
    for r in rows:
        acc = r["key"] == "0.1"
        col = ACCENT if acc else CONTEXT
        lo, hi = r["ci"]
        a1.plot([r["x"], r["x"]], [lo, hi], color=col, linewidth=2.0,
                solid_capstyle="round", zorder=3)
        a1.plot([r["x"]], [r["rho"]], "o", markersize=9 if acc else 8,
                color=col, markeredgecolor=SURFACE, markeredgewidth=2.0,
                zorder=4)
        a1.annotate(f"{r['rho']:+.3f}", (r["x"], hi), textcoords="offset points",
                    xytext=(0, 7), ha="center", fontsize=8,
                    color=INK if acc else INK2,
                    fontweight="bold" if acc else "normal")
    los = [r["ci"][0] for r in rows]
    his = [r["ci"][1] for r in rows]
    span = max(his) - min(los)
    a1.set_ylim(min(los) - 0.10 * span, max(his) + 0.22 * span)
    a1.set_ylabel("Spearman rho (g vs observed difference)",
                  fontsize=9, color=INK2)
    a1.set_title("H2 across the regularisation sweep: the sign of the "
                 "relationship depends on lambda",
                 fontsize=11, color=INK, loc="left", pad=26)
    a1.annotate("lambda = 0.1 is the only column where all 360 units survive",
                xy=(0.0, 1.015), xycoords="axes fraction", fontsize=8.5,
                color=ACCENT, ha="left", va="bottom")

    for r in rows:
        acc = r["key"] == "0.1"
        col = ACCENT if acc else CONTEXT
        w = r["x"] * 0.28
        a2.bar(r["x"], r["units"], width=w, color=col, zorder=3,
               edgecolor=SURFACE, linewidth=2.0)
        a2.annotate(f"{r['units']}", (r["x"], r["units"]),
                    textcoords="offset points", xytext=(0, 4), ha="center",
                    fontsize=8, color=INK if acc else INK2,
                    fontweight="bold" if acc else "normal")
    a2.axhline(360, color=AXIS, linewidth=1.0, linestyle=(0, (2, 3)), zorder=2)
    a2.annotate("360 registered", (1.2e-4, 360), textcoords="offset points",
                xytext=(0, 4), fontsize=7.5, color=MUTED)
    a2.set_ylim(0, 420)
    a2.set_ylabel("units retained", fontsize=9, color=INK2)
    a2.set_xlabel("lambda", fontsize=9, color=INK2)

    ticks = [1e-4, 1e-3, 1e-2, 1e-1, fromc["x"]]
    a2.set_xticks(ticks)
    a2.set_xticklabels(["1e-4", "1e-3", "1e-2", "1e-1", "from C"])
    a2.set_xlim(5e-5, 10 ** (np.log10(1e-1) + 1.15))

    stamp(fig, "source: results/audits/h2_h3_report.json  |  360 registered "
               "units, 7,200 per-seed rows  |  both hypotheses return NOT "
               "ESTABLISHED (no breach-free lambda)")
    save(fig, "fig1_h2_lambda")


# ------------------------------------------------------------------ fig 2

def fig_h1_paired():
    series = {}
    for ds in ("churn", "fraud"):
        q = load(QDIR / f"{ds}_matched_n{CONFIRMATORY_N}.jsonl")
        c = load(CDIR / f"{ds}_matched_n{CONFIRMATORY_N}.jsonl")
        if q is None or c is None:
            raise SystemExit(f"missing records for {ds}")
        fatal, _notes, qbc, cbc, _arm = integrity(q, c, ds, CONFIRMATORY_N)
        if fatal:
            raise SystemExit(f"integrity failure on {ds}: {fatal[0]}")
        seeds = sorted({r["seed"] for r in q})
        rows = paired_series(qbc, cbc, PRIMARY_CELL[ds], seeds)
        series[ds] = np.array([r["d_normap"] for r in rows], dtype=float)

    allv = np.concatenate(list(series.values()))
    pad = 0.06 * (allv.max() - allv.min())
    lo, hi = allv.min() - pad, allv.max() + pad

    fig, axes = plt.subplots(2, 1, figsize=(7.2, 3.2), sharex=True,
                             gridspec_kw={"hspace": 0.38})
    fig.patch.set_facecolor(SURFACE)
    rng = np.random.default_rng(0)        # fixed: a figure must be reproducible

    for ax, ds in zip(axes, ("churn", "fraud")):
        style(ax)
        v = series[ds]
        ax.axvline(0.0, color=AXIS, linewidth=1.2, zorder=2)
        ax.scatter(v, rng.uniform(-0.22, 0.22, v.size), s=34, color=CONTEXT,
                   alpha=0.75, linewidths=1.5, edgecolors=SURFACE, zorder=3)
        m = float(v.mean())
        sd = float(v.std(ddof=1))
        half = 2.093 * sd / np.sqrt(v.size)      # t(.975, 19)
        ax.plot([m - half, m + half], [0, 0], color=ACCENT, linewidth=2.0,
                solid_capstyle="round", zorder=4)
        ax.plot([m], [0], "o", markersize=10, color=ACCENT,
                markeredgecolor=SURFACE, markeredgewidth=2.0, zorder=5)
        ax.annotate(f"mean {m:+.4f}", (m, 0), textcoords="offset points",
                    xytext=(0, 14), ha="center", fontsize=8.5,
                    color=INK, fontweight="bold")
        cell = PRIMARY_CELL[ds]
        ax.set_ylabel(f"{ds}\n{cell[0]}/{cell[1]}", fontsize=9, color=INK2,
                      rotation=0, ha="right", va="center", labelpad=28)
        ax.set_yticks([])
        ax.set_ylim(-0.42, 0.52)
        ax.set_xlim(lo, hi)

    axes[0].set_title("H1 at the primary cells: twenty paired seeds, one "
                      "shared scale",
                      fontsize=11, color=INK, loc="left", pad=22)
    axes[0].annotate("negative favours the classical kernel",
                     xy=(0.0, 1.03), xycoords="axes fraction", fontsize=8.5,
                     color=INK2, ha="left", va="bottom")
    axes[1].set_xlabel("paired difference in normAP  (quantum minus classical)",
                       fontsize=9, color=INK2)

    stamp(fig, "source: results/runs/{quantum,classical}/*_matched_n250.jsonl "
               "via primary_tests.paired_series  |  one scale for both panels: "
               "fraud's null is not rescaled to fill its panel")
    save(fig, "fig2_h1_paired")


# ------------------------------------------------------------------ fig 3

def fig_churn_exploratory():
    d = json.loads(EXPL.read_text())
    fams = d["datasets"]["churn"]
    groups = [
        ("qubit count", "the qubit-count trend", lambda l: f"{l} qubits"),
        ("mapping", "per-mapping breakdowns", lambda l: str(l)),
        ("training size", "the training-size comparison",
         lambda l: f"{l} per class"),
    ]
    items, seps, labels = [], [], []
    y = 0
    for gname, key, fmt in groups:
        rows = [r for r in fams[key]["rows"] if r.get("estimable")]
        for r in rows:
            items.append((y, r, gname))
            labels.append(fmt(r["level"]))
            y += 1
        seps.append((gname, y - len(rows), y - 1))
        y += 1

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    ax.axvline(0.0, color=AXIS, linewidth=1.2, zorder=2)

    for yy, r, _g in items:
        sig = bool(r.get("rejects_after_holm"))
        col = ACCENT if sig else CONTEXT
        ax.plot([0, r["mean"]], [yy, yy], color=col, linewidth=2.0,
                solid_capstyle="round", zorder=3)
        ax.plot([r["mean"]], [yy], "o", markersize=9 if sig else 8, color=col,
                markeredgecolor=SURFACE, markeredgewidth=2.0, zorder=4)
        if sig:   # selective labels: only what survived correction
            ax.annotate(f"{r['mean']:+.4f}   Holm {r['p_holm']:.1e}",
                        (r["mean"], yy), textcoords="offset points",
                        xytext=(-10, 0), ha="right", va="center",
                        fontsize=8, color=INK, fontweight="bold")

    ax.set_yticks([i[0] for i in items])
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.invert_yaxis()
    for gname, y0, y1 in seps:
        ax.annotate(gname, xy=(1.005, 1 - ((y0 + y1) / 2 + 0.5) / y),
                    xycoords="axes fraction", fontsize=8.5, color=MUTED,
                    rotation=270, ha="left", va="center")
    # The leftmost bar's label is drawn outside its marker; without this the
    # longest bar (-0.0659) pushed its label over the y tick labels.
    xs = [r["mean"] for _y, r, _g in items]
    rng_x = max(max(xs), 0.0) - min(xs)
    ax.set_xlim(min(xs) - 0.62 * rng_x, max(max(xs), 0.0) + 0.04 * rng_x)
    ax.set_xlabel("mean paired difference in normAP  "
                  "(quantum minus classical)", fontsize=9, color=INK2)
    ax.set_title("Churn, exploratory: the deficit is absent under random "
                 "projection", fontsize=11, color=INK, loc="left", pad=24)
    ax.annotate("accent = survives Holm correction within its family; "
                "grey = does not",
                xy=(0.0, 1.025), xycoords="axes fraction", fontsize=8.5,
                color=INK2, ha="left", va="bottom")

    stamp(fig, "source: results/analysis/exploratory_sweep.json  |  "
               "EXPLORATORY: Holm-corrected within each family; bears on no "
               "confirmatory hypothesis  |  50 per class is excluded from "
               "testing by pre-registration line 104")
    save(fig, "fig3_churn_exploratory")


# ------------------------------------------------------------------ main

def check():
    bad = 0
    for p in (H2, EXPL):
        ok = p.exists()
        print(f"  {'ok  ' if ok else 'FAIL'} {p.relative_to(ROOT)}")
        bad += 0 if ok else 1
    for ds in ("churn", "fraud"):
        for base, d in (("quantum", QDIR), ("classical", CDIR)):
            p = d / f"{ds}_matched_n{CONFIRMATORY_N}.jsonl"
            ok = p.exists()
            print(f"  {'ok  ' if ok else 'FAIL'} {p.relative_to(ROOT)}")
            bad += 0 if ok else 1
    print(f"  matplotlib {matplotlib.__version__}")
    print("\n" + ("inputs are present" if not bad else f"{bad} missing"))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="validate inputs only; draw nothing")
    args = ap.parse_args()
    if args.check:
        sys.exit(check())
    print("fig 1: H2 across lambda")
    fig_h2_lambda()
    print("fig 2: H1 paired differences")
    fig_h1_paired()
    print("fig 3: churn exploratory families")
    fig_churn_exploratory()
    print("\nLook at all three before using them. The palette was validated; "
          "layout was not.")


if __name__ == "__main__":
    main()
