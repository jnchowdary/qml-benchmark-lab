#!/usr/bin/env python3
"""Do the regression tests actually catch the defects they claim to? (week 8)

WHY THIS EXISTS
---------------
`tests/test_geometric_tests.py` passed 28 of 28 on its first run. Its docstring
claimed each case "fails against the shipped behaviour" and nothing had checked
that claim. A regression test that passes against both the fixed and the broken
code is decoration, and this project has already published one table built on an
unchecked claim.

So each fix is reverted one at a time, the test that claims to catch it is run,
and the run MUST fail. A surviving mutant means the test does not test what its
name says.

THIS FOUND ONE IMMEDIATELY, WHICH IS THE ARGUMENT FOR IT
---------------------------------------------------------
`TestH3::test_refuses_a_verdict_where_h2_refuses` passed against code with the
MIN_UNITS guard deleted. It built eight units with g = 1..8, which the g = 2
split divides six above and two below, so `min(above, below) < 3` refused on the
degenerate partition and the guard the test claimed to pin was never reached.
The test asserted a true outcome through the wrong code path. It now balances the
split and asserts WHICH guard fired.

Every test in the suite has a mutant. A test without one has never been shown to
fail against anything, which is precisely the state that test was in.

WHAT IT DOES NOT DO
-------------------
It does not prove the tests are sufficient, only that they are not vacuous.
Killed mutants are a lower bound; surviving mutants are definite gaps.

Nothing is left modified. Every touched file is restored after every mutation,
including on failure, and each restore is verified by hash before exit.

Usage:
    PYTHONPATH=src python scripts/mutation_check.py
    PYTHONPATH=src python scripts/mutation_check.py --list
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests" / "test_geometric_tests.py"
GT = "scripts/geometric_tests.py"
PT = "scripts/primary_tests.py"


def M(name, why, old, new, test, file=GT):
    """One mutant: revert `old` to `new` in `file`, then `test` MUST fail."""
    return {"name": name, "why": why, "old": old, "new": new, "test": test,
            "file": file}


MUTANTS = [
    # ---- the twelve defects week 7 section 6 records ----------------------
    M("median -> mean",
      "D7 chose the median so one heavy-tailed seed cannot carry a unit",
      '"g": float(np.median(gs)), "g_iqr": float(q3 - q1)',
      '"g": float(np.mean(gs)), "g_iqr": float(q3 - q1)',
      "TestAggregation::test_unit_g_is_the_median_not_the_mean"),

    M("d over all seeds, not survivors",
      "D8(a): a median from one seed set paired against a mean from another",
      '"d": float(ds.mean()), "seeds": len(kept)',
      '"d": float(np.mean([float(r["d_normap"]) for r in rs])), "seeds": len(kept)',
      "TestAggregation::test_observed_difference_uses_only_surviving_seeds"),

    M("global ceiling instead of per-row",
      "sqrt(n_train) is 18.71 at n=250 and 11.83 at n=100; one constant is wrong",
      'if g > float(r["ceiling"]):',
      'if g > 18.708286933869708:',
      "TestAggregation::test_ceiling_is_per_row_not_global"),

    M("breach count without its denominator",
      "the bare count that published 9/8 in D5",
      "    return units, excluded, breaches, total",
      "    return units, excluded, breaches",
      "TestAggregation::test_breach_count_is_returned_with_its_denominator"),

    M("from_C reads the g dict",
      "lambda-from-C varies by seed so it cannot share a key in `g`",
      'return float(row["g_from_C"]) if col == "from_C" else float(row["g"][col])',
      'return float(row["g"][col]) if col != "from_C" else float(row["g"]["0.1"])',
      "TestAggregation::test_from_C_column_reads_its_own_field"),

    M("no rho clamp in the Fisher z",
      "arctanh(1) = inf, no interval, and the strongest result reads NOT SUPPORTED",
      "    cap = 1.0 - 1.0 / (2.0 * n)\n    z = np.arctanh(np.clip(rho, -cap, cap))",
      "    if abs(rho) >= 1.0:\n        return None, None\n    z = np.arctanh(rho)",
      "TestH2::test_perfect_correlation_is_supported_not_rejected"),

    M("H3 verdict below MIN_UNITS",
      "eight units gave H3 a verdict while H2 on the same eight refused",
      "    if len(units) < MIN_UNITS:\n        # Same floor as H2.",
      "    if False:\n        # Same floor as H2.",
      "TestH3::test_refuses_a_verdict_where_h2_refuses"),

    M("degenerate partition reported as a null",
      "a fixed threshold that stops partitioning has stopped being a test",
      "    if min(len(above), len(below)) < 3:",
      "    if min(len(above), len(below)) < 0:",
      "TestH3::test_degenerate_partition_is_not_estimable_not_null"),

    M("p underflow printed as zero",
      "0.00e+00 reads as a certainty no finite sample supplies",
      'return "<1e-300" if p == 0.0 else f"{p:.2e}"',
      'return f"{p:.2e}"',
      "TestDisplay::test_underflowed_p_is_not_printed_as_zero"),

    M("arm dropped from the resume key",
      "two arms silently sharing one file under one label",
      "        if seen_arms - {arm}:",
      "        if False:",
      "TestSweepPlumbing::test_sweep_refuses_to_mix_arms_in_one_file"),

    M("no NaN guard on a constant input",
      "rejects = bool(nan < 0.05) = False, so an undefined rho reads NOT SUPPORTED",
      "    if not np.isfinite(rho):",
      "    if False:",
      "TestH2::test_constant_input_is_not_estimable"),

    # ---- the nineteen that had no mutant until week 8 ---------------------
    M("IQR always zero",
      "a unit whose seeds disagree about g is evidence about g (D7)",
      "        q1, q3 = np.percentile(gs, [25, 75])",
      "        q1, q3 = np.percentile(gs, [50, 50])",
      "TestAggregation::test_iqr_is_reported_with_every_unit"),

    M("excluded unit loses its seed count",
      "D7 requires exclusions to be counted and named, never silently dropped",
      '"of_seeds": len(rs), "reason": "below MIN_SEEDS"})',
      '"of_seeds": 0, "reason": "below MIN_SEEDS"})',
      "TestAggregation::test_unit_below_min_seeds_is_excluded_and_named"),

    M("precision floor moved below every difference",
      "D2's floor separates a measurement from arithmetic noise",
      "FLOOR = 1e-3                      # D2's precision floor, in AP",
      "FLOOR = 1e-12                     # D2's precision floor, in AP",
      "TestH2::test_units_below_the_floor_are_counted_as_such"),

    M("D8(b) subset never computed",
      "a rank correlation among units below the floor is a correlation in noise",
      "    sub = None\n    if len(resolved) >= MIN_UNITS:",
      "    sub = None\n    if False:",
      "TestH2::test_above_floor_subset_is_computed"),

    M("H2 guard below MIN_UNITS removed",
      "a rank test on a handful of units is not estimable",
      '    if len(units) < MIN_UNITS:\n        return {"label": label,',
      '    if False:\n        return {"label": label,',
      "TestH2::test_not_estimable_below_min_units"),

    M("constant_g flag hardcoded false",
      "the caller cannot tell which input was constant",
      '                "constant_g": bool(len(set(g)) == 1),',
      '                "constant_g": False,',
      "TestH2::test_constant_g_is_also_not_estimable"),

    M("bootstrap seed not fixed",
      "this interval feeds a verdict, so it must be identical on every re-run",
      "    rng = np.random.default_rng(seed)",
      "    rng = np.random.default_rng()",
      "TestH3::test_median_diff_ci_is_deterministic"),

    M("verdict always SUPPORTED",
      "a stage that finds a result in noise is worse than one that finds none",
      '    return "SUPPORTED" if all(res.get(k) for k in keys) else "NOT SUPPORTED"',
      '    return "SUPPORTED"',
      "TestNegativeControl::test_no_signal_is_not_supported_on_both"),

    M("signed secondary dropped",
      "D8(c): |d| cannot separate quantum winning from quantum losing",
      '               signed_secondary={"U": float(sa), "p": float(sp),',
      '               signed_secondary_GONE={"U": float(sa), "p": float(sp),',
      "TestH3::test_signed_secondary_is_always_reported"),

    M("spearman_ci refuses at realistic n",
      "the interval the verdict rule needs must exist at the sizes it is used at",
      "    if n < 5 or not np.isfinite(rho):",
      "    if n < 100 or not np.isfinite(rho):",
      "TestH2::test_spearman_ci_is_finite_at_rho_one"),

    M("control B expects g(K,K) = 1",
      "the expectation that was wrong before the code was; it is mu/(mu+lam)",
      '    off = max(abs(same["same"][l] - mu / (mu + l)) for l in probe)',
      '    off = max(abs(same["same"][l] - 1.0) for l in probe)',
      "TestNegativeControl::test_all_nine_script_controls_pass"),

    M("hoisted g drops the K_Q normalisation",
      "the 4x saving is worth nothing if it moves a digit",
      "        sq = _matrix_sqrt_psd(normalise_kernel(np.asarray(K_q, dtype=float)))",
      "        sq = _matrix_sqrt_psd(np.asarray(K_q, dtype=float))",
      "TestFastPath::test_hoisted_g_equals_the_module_exactly"),

    M("g loses its square root",
      "g is the sqrt of a spectral norm, not the norm",
      "        out[name] = {lam: float(np.sqrt(max(",
      "        out[name] = {lam: float((max(",
      "TestFastPath::test_identical_kernels_give_mu_over_mu_plus_lambda_not_one"),

    M("--test removed from the CLI",
      "it was in the docstring and not in argparse, so --test failed",
      '    ap.add_argument("--test", action="store_true",',
      '    ap.add_argument("--test-GONE", action="store_true",',
      "TestSweepPlumbing::test_cli_accepts_test_and_units"),

    M("check_inputs always passes",
      "the nine controls never open a file; this is the only thing that does",
      "    return ok",
      "    return True",
      "TestSweepPlumbing::test_check_inputs_fails_on_a_missing_file"),

    M("H3 threshold retuned",
      "g = 2 is registered and is never retuned",
      "G_SPLIT = 2.0                                # H3 threshold, registered.",
      "G_SPLIT = 3.0                                # H3 threshold, registered.",
      "TestH3::test_split_is_the_registered_threshold"),

    M("registered universe miscounted",
      "2 datasets x 3 mappings x 5 qubit counts x 3 sizes x 4 settings = 360",
      "REGISTERED_UNITS = 360",
      "REGISTERED_UNITS = 400",
      "TestSweepPlumbing::test_registered_universe_is_360_units"),

    M("lambda columns not the frozen sweep",
      "D5 freezes (1e-1, 1e-2, 1e-3, 1e-4) plus lambda-from-C",
      'LAM_COLS = tuple(f"{l:g}" for l in LAMBDAS) + ("from_C",)',
      'LAM_COLS = tuple(f"{l:g}" for l in LAMBDAS)',
      "TestSweepPlumbing::test_lambda_columns_are_the_frozen_sweep_plus_from_C"),

    M("primary_tests.load accepts a str",
      "the AttributeError that stopped the first real sweep run",
      "def load(path):\n    if not path.exists():",
      "def load(path):\n    path = Path(path)\n    if not path.exists():",
      "TestSweepPlumbing::test_load_takes_a_path_not_a_string",
      file=PT),
]


def run_test(nodeid):
    cmd = [sys.executable, "-m", "pytest", f"{TESTS}::{nodeid}",
           "-q", "--no-header", "-x", "-p", "no:cacheprovider"]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    return r.returncode, (r.stdout + r.stderr)


def coverage_report():
    """Which tests have no mutant, i.e. whose non-vacuity is unproven."""
    import re
    covered = {m["test"].split("::")[-1] for m in MUTANTS}
    allt = set(re.findall(r"def (test_\w+)", TESTS.read_text()))
    return covered, allt


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--list", action="store_true", help="show the mutants and stop")
    args = ap.parse_args()

    if args.list:
        for i, m in enumerate(MUTANTS, 1):
            print(f"  {i:2d}. {m['name']}  [{m['file']}]\n      {m['why']}"
                  f"\n      -> {m['test']}")
        return

    covered, allt = coverage_report()
    stray = covered - allt
    uncovered = allt - covered

    files = sorted({m["file"] for m in MUTANTS})
    originals = {f: (ROOT / f).read_text() for f in files}
    digests = {f: hashlib.sha1(v.encode()).hexdigest()[:8]
               for f, v in originals.items()}
    print(f"\nMUTATION CHECK, {len(MUTANTS)} mutants across {len(files)} file(s)")
    for f in files:
        print(f"    {f}  {digests[f]}")
    print(f"\n  coverage: {len(covered)} of {len(allt)} tests have a mutant")
    if stray:
        print(f"  MUTANTS NAMING A TEST THAT DOES NOT EXIST: {sorted(stray)}")
    if uncovered:
        print(f"  tests with NO mutant (non-vacuity unproven): {sorted(uncovered)}")
    print("\n  Each fix is reverted, its test is run, and the run MUST fail.")
    print("  A SURVIVOR means the test does not test what its name says.\n")

    survivors, missing, killed = [], [], []
    try:
        for m in MUTANTS:
            name, test, f = m["name"], m["test"], m["file"]
            src, path = originals[f], ROOT / f
            if src.count(m["old"]) != 1:
                print(f"  [SKIP  ] {name}\n           pattern found "
                      f"{src.count(m['old'])}x in {f}, expected once -- the code "
                      f"moved, so this mutant is stale")
                missing.append(name)
                continue
            path.write_text(src.replace(m["old"], m["new"]))
            code, _ = run_test(test)
            if code == 0:
                print(f"  [SURVIVED] {name}\n             {m['why']}\n"
                      f"             {test} still passes against the broken code")
                survivors.append((name, test))
            else:
                print(f"  [killed] {name}")
                killed.append(name)
            path.write_text(src)
    finally:
        for f in files:
            (ROOT / f).write_text(originals[f])
            back = hashlib.sha1((ROOT / f).read_text().encode()).hexdigest()[:8]
            assert back == digests[f], (
                f"RESTORE FAILED: {f} is {back}, expected {digests[f]}. "
                f"Restore it from git before doing anything else.")
            print(f"\n  restored {f} -> {back} (matches)")

    print(f"\n  {len(killed)} killed, {len(survivors)} survived, "
          f"{len(missing)} stale")
    if survivors:
        print("\n  SURVIVING MUTANTS -- these tests do not catch their defect:")
        for name, test in survivors:
            print(f"    {name}  ({test})")
        print("\n  A surviving mutant is a definite gap. Fix the test, not the "
              "mutant.")
    else:
        print("\n  Every mutant was killed by the test that claims to catch it.")
    print("\n  This is a lower bound: killed mutants are not proof of coverage,")
    print("  only proof that these particular tests are not vacuous.")
    sys.exit(1 if (survivors or missing or stray) else 0)


if __name__ == "__main__":
    main()
