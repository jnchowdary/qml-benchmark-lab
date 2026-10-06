"""The confirmatory test's machinery, locked down before it is used once.

WHY THIS FILE EXISTS
--------------------
`scripts/primary_tests.py` implements section 4 of the
pre-registration: which record each arm contributes, which endpoints decide,
and when the analysis must refuse to produce a verdict at all. Each of those is
a place where a plausible-looking implementation silently answers a different
question than the one registered:

  * selecting the arm by the TEST score instead of the inner-CV score turns a
    held-out estimate into a maximum over four settings, which is biased upward
    and would manufacture an advantage;
  * breaking an inner-CV tie by dict order makes the verdict depend on which
    cells happened to be resumed;
  * treating "either endpoint rejects" as the rule inflates type I error, which
    is the exact thing the intersection-union rule was chosen to avoid;
  * carrying on past a fingerprint mismatch compares two kernels scored on
    different test points and calls the difference a result.

None of these would raise an exception in a real run. They would produce a
number. So they are tested.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import primary_tests as tph  # noqa: E402
from qbench.metrics import chance_average_precision  # noqa: E402

FP = "a" * 16


def qrec(seed, *, setting="angle-r1", inner=0.60, ap=0.70, roc=0.70,
         mapping="pca", nq=12, fingerprint=FP, **kw):
    r = {"method": f"quantum-{setting}", "setting": setting, "mapping": mapping,
         "n_qubits": nq, "seed": seed, "n_train": 350, "n_test": 150,
         "test_base_rate": 0.5, "shuffled": False, "device": "lightning.qubit",
         "git_commit": "0b796a3", "inner_score": inner, "track": "matched",
         "test_average_precision": ap, "test_roc_auc": roc,
         "final_converged": True, "final_fallback_rank": 0,
         "circuit_evaluations": 61075, "simulator_executions": 500,
         "test_label_fingerprint": fingerprint}
    r.update(kw)
    return r


def crec(seed, *, method="linear", inner=0.60, ap=0.70, roc=0.70,
         mapping="pca", nq=12, fingerprint=FP, **kw):
    r = {"method": method, "mapping": mapping, "n_qubits": nq, "seed": seed,
         "n_train": 350, "n_test": 150, "test_base_rate": 0.5, "shuffled": False,
         "git_commit": "0b2aef4", "inner_score": inner, "track": "matched",
         "test_average_precision": ap, "test_roc_auc": roc,
         "final_converged": True, "final_fallback_rank": 0,
         "test_label_fingerprint": fingerprint}
    r.update(kw)
    return r


# ------------------------------------------------------- arm selection

def test_selection_ignores_the_test_score():
    """The setting with the best test score but the worst inner score must
    not be the one that enters the test. This is the whole reason the outer
    test set is touched once, after selection."""
    records = [
        qrec(0, setting="angle-r1", inner=0.80, ap=0.60),   # best inner, mediocre test
        qrec(0, setting="iqp-r2", inner=0.40, ap=0.99),     # best test, worst inner
    ]
    assert tph.best_by_inner(records)["setting"] == "angle-r1"
    assert tph.best_by_inner(list(reversed(records)))["setting"] == "angle-r1"


def test_inner_cv_tie_is_broken_deterministically():
    """Identical inner scores must not let file order decide the verdict.
    Resuming a run changes record order; it must not change the result."""
    a = qrec(0, setting="angle-r1", inner=0.5, ap=0.10)
    b = qrec(0, setting="iqp-r1", inner=0.5, ap=0.90)
    assert tph.best_by_inner([a, b])["setting"] == tph.best_by_inner([b, a])["setting"]


def test_normap_uses_exact_chance_not_the_base_rate():
    """A random ranker scores 0.5154 on 150 balanced points, not 0.5. Dividing
    by (1 - base) instead of (1 - chance) inflates every normAP, and worst on
    the smallest test sets, which is where the learning curve lives."""
    r = qrec(0, ap=0.70)
    chance = chance_average_precision(150, 75)
    assert chance > 0.5
    assert tph.norm_ap(r) == pytest.approx((0.70 - chance) / (1 - chance))
    naive = (0.70 - 0.5) / (1 - 0.5)
    assert tph.norm_ap(r) < naive


# ------------------------------------------------- the decision rule

def _jitter(base, spread, n=20, seed=0):
    """A series with real spread, because a constant series is a degenerate
    input the solver handles differently than any real run."""
    import random
    rng = random.Random(seed)
    return [base + rng.gauss(0, spread) for _ in range(n)]


def _series(d_ap, d_roc):
    return [{"seed": i, "q_method": "angle-r1", "c_method": "linear",
             "d_normap": a, "d_roc": b, "q_normap": a, "c_normap": 0.0,
             "q_roc": b, "c_roc": 0.0}
            for i, (a, b) in enumerate(zip(d_ap, d_roc))]


def test_intersection_union_needs_both_endpoints(capsys):
    """One endpoint rejecting is not a rejection. If it were, the rule would be
    a union without the alpha split the union rule requires."""
    strong = _jitter(0.05, 0.01, seed=1)      # normAP: rejects easily
    flat = _jitter(0.0, 0.02, seed=2)         # ROC-AUC: nowhere near
    rows = _series(strong, flat)
    summary = tph.report_primary("churn", 250, rows, confirmatory=True)
    assert summary["normap"]["p_wilcoxon"] < 0.05
    assert summary["roc"]["p_wilcoxon"] > 0.05
    assert summary["reject"] is False
    assert "DO NOT REJECT" in capsys.readouterr().out


def test_both_endpoints_rejecting_is_a_rejection():
    rows = _series(_jitter(0.05, 0.01, seed=3), _jitter(0.04, 0.01, seed=4))
    summary = tph.report_primary("churn", 250, rows, confirmatory=True)
    assert summary["reject"] is True


def test_discordant_directions_are_not_called_an_advantage(capsys):
    """Both endpoints rejecting but pointing opposite ways is a finding about
    the endpoints, not evidence of an advantage."""
    rows = _series(_jitter(0.05, 0.01, seed=5), _jitter(-0.04, 0.01, seed=6))
    summary = tph.report_primary("churn", 250, rows, confirmatory=True)
    assert summary["reject"] is False
    assert "disagree in direction" in capsys.readouterr().out


def test_no_rejection_is_reported_as_an_exclusion_bound(capsys):
    """Section 8: never 'no difference found'."""
    rows = _series(_jitter(0.0, 0.02, seed=7), _jitter(0.0, 0.02, seed=8))
    summary = tph.report_primary("fraud", 250, rows, True)
    assert summary["reject"] is False
    out = capsys.readouterr().out
    assert "exclusion bound" in out
    # D6's PRIMARY-CELL paired figure, 0.0063, not section 5's registered 0.0059.
    # This assertion follows D6's independently measured table; it is not chosen
    # to make the code pass. The registered value was wrong by 2.3x on this arm,
    # and until 6 October 2026 this test pinned the script to it.
    assert "0.0063" in out
    assert "0.0059" not in out


def test_wilcoxon_is_the_test_and_t_is_only_reported():
    """The summary must carry both, so a disagreement between them is visible
    rather than hidden behind whichever was implemented."""
    e = tph.endpoint_test([0.01, 0.02, -0.005, 0.03, 0.015, 0.02, 0.01, 0.025])
    assert "p_wilcoxon" in e and "p_t" in e


def test_holm_is_conservative_and_monotone():
    raw = [0.001, 0.01, 0.04, 0.9]
    adj = tph.holm(raw)
    assert all(a >= r for a, r in zip(adj, raw))
    assert adj == sorted(adj)
    assert max(adj) <= 1.0


# ------------------------------------------------------------ halting

def _pair(qkw=None, ckw=None):
    q = [qrec(s, **(qkw or {})) for s in range(3)]
    c = [crec(s, **(ckw or {})) for s in range(3)]
    return q, c


def test_clean_pair_has_no_fatal_problems():
    q, c = _pair()
    fatal, _, _, _, _ = tph.integrity(q, c, "churn", 250)
    assert fatal == []


def test_fingerprint_mismatch_is_fatal():
    """Two kernels scored on different test points cannot be paired, and
    section 4 says the analysis aborts rather than working around it."""
    q, c = _pair()
    q[1]["test_label_fingerprint"] = "b" * 16
    fatal, _, _, _, _ = tph.integrity(q, c, "churn", 250)
    assert any("fingerprint" in f for f in fatal)


def test_wrong_backend_is_fatal():
    q, c = _pair()
    q[0]["device"] = "default.qubit"
    fatal, _, _, _, _ = tph.integrity(q, c, "churn", 250)
    assert any("backend" in f for f in fatal)


def test_shuffled_records_in_a_real_file_are_fatal():
    q, c = _pair()
    q[2]["shuffled"] = True
    fatal, _, _, _, _ = tph.integrity(q, c, "churn", 250)
    assert any("shuffled" in f for f in fatal)


def test_non_converged_final_model_is_fatal():
    q, c = _pair()
    q[0]["final_converged"] = False
    fatal, _, _, _, _ = tph.integrity(q, c, "churn", 250)
    assert any("converge" in f for f in fatal)


def test_missing_classical_counterpart_is_fatal():
    q, _ = _pair()
    fatal, _, _, _, _ = tph.integrity(q, [], "churn", 250)
    assert any("no classical counterpart" in f for f in fatal)


def test_paired_series_pairs_on_the_seed_not_on_order():
    """A reversed classical file must give the same paired differences."""
    q = [qrec(s, ap=0.70 + 0.01 * s) for s in range(5)]
    c = [crec(s, ap=0.60 + 0.02 * s) for s in range(5)]
    _, _, qc, cc, _ = tph.integrity(q, c, "churn", 250)
    _, _, qc2, cc2, _ = tph.integrity(list(reversed(q)), list(reversed(c)), "churn", 250)
    seeds = list(range(5))
    a = [r["d_normap"] for r in tph.paired_series(qc, cc, ("pca", 12), seeds)]
    b = [r["d_normap"] for r in tph.paired_series(qc2, cc2, ("pca", 12), seeds)]
    assert a == pytest.approx(b)
    assert len(a) == 5


# ------------------------------------- the post-hoc arm cannot self-promote

def test_bandwidth_arm_is_detected_from_the_records():
    """Not from a command-line flag. A post-hoc arm must be unable to present
    itself as confirmatory even if someone runs it with the default options."""
    q, c = _pair(qkw={"bandwidth_arm": True, "bandwidth": 0.25})
    fatal, notes, _, _, is_arm = tph.integrity(q, c, "churn", 250)
    assert fatal == []
    assert is_arm is True
    assert any("EXPLORATORY BANDWIDTH ARM" in n for n in notes)


def test_registered_records_are_not_flagged_as_an_arm():
    q, c = _pair()
    *_, is_arm = tph.integrity(q, c, "churn", 250)
    assert is_arm is False


# ------------------------------- the two exploratory families, as data
#
# Until week 12 report_per_setting and report_sweep returned None, printed
# three rounded numbers per level, and had no test of any kind. The numbers
# existed only in results/analysis/primary_tests.log, at four decimal places,
# with n, median, sd, the confidence interval and the sensitivity t-test absent
# because they are never printed. These tests pin the structured return and the
# two places where printing and data could disagree.


def _cells(settings, seeds, *, mapping="pca", nq=12):
    """q_by_cell / c_by_cell for one cell, keyed (mapping, nq, seed) as the
    script keys them. Quantum AP varies by setting AND seed so every sd > 0."""
    q_by, c_by = {}, {}
    for seed in seeds:
        k = (mapping, nq, seed)
        q_by[k] = [qrec(seed, setting=s, mapping=mapping, nq=nq,
                        inner=0.60 + 0.001 * i,
                        ap=0.70 + 0.01 * i + 0.002 * seed)
                   for i, s in enumerate(settings)]
        c_by[k] = [crec(seed, method="linear", mapping=mapping, nq=nq,
                        ap=0.70 + 0.001 * seed)]
    return q_by, c_by


def test_per_setting_returns_every_level_it_prints(capsys):
    settings = ["angle-r1", "angle-r2", "iqp-r1", "iqp-r2"]
    q_by, c_by = _cells(settings, range(6))
    fam = tph.report_per_setting("churn", q_by, c_by, ("pca", 12), list(range(6)))
    assert fam["holm_family_size"] == 4
    assert [lv["setting"] for lv in fam["levels"]] == settings
    for lv in fam["levels"]:
        # The fields the log never carried.
        for f in ("n", "mean", "median", "sd", "ci", "p_wilcoxon", "p_t", "p_holm"):
            assert f in lv, f
        assert lv["n"] == 6
    printed = capsys.readouterr().out
    for lv in fam["levels"]:
        assert f"{lv['mean']:+.4f}" in printed


def test_per_setting_holm_values_belong_to_their_own_level():
    """holm() returns adjusted p in input order. If a future edit sorts the
    rows for display and zips the sorted rows against the unsorted adjustment,
    every level keeps the wrong Holm value and nothing raises."""
    settings = ["angle-r1", "angle-r2", "iqp-r1", "iqp-r2"]
    q_by, c_by = _cells(settings, range(8))
    fam = tph.report_per_setting("churn", q_by, c_by, ("pca", 12), list(range(8)))
    expect = tph.holm([lv["p_wilcoxon"] for lv in fam["levels"]])
    assert [lv["p_holm"] for lv in fam["levels"]] == pytest.approx(expect)


def test_per_setting_family_size_is_computed_not_hardcoded_four(capsys):
    """The old header printed the literal 4. It was right for every run made,
    and it was never derived from the data."""
    q_by, c_by = _cells(["angle-r1", "iqp-r1", "iqp-r2"], range(5))
    fam = tph.report_per_setting("churn", q_by, c_by, ("pca", 12), list(range(5)))
    assert fam["holm_family_size"] == 3
    assert "family of 3" in capsys.readouterr().out


def test_per_setting_names_a_setting_it_could_not_test():
    q_by, c_by = _cells(["angle-r1", "angle-r2"], range(5))
    # A third setting present at one seed only: one paired diff, so no test.
    k = ("pca", 12, 0)
    q_by[k] = q_by[k] + [qrec(0, setting="iqp-r2", ap=0.80)]
    fam = tph.report_per_setting("churn", q_by, c_by, ("pca", 12), list(range(5)))
    assert fam["holm_family_size"] == 2
    assert fam["settings_untested"] == ["iqp-r2"]
    assert "iqp-r2" not in [lv["setting"] for lv in fam["levels"]]
    assert "iqp-r2" in fam["settings_attempted"]


def test_sweep_counts_the_cells_it_skipped():
    """The header says "all cells". A cell with fewer than two paired series is
    silently dropped, so the count has to be in the record."""
    q_by, c_by = _cells(["angle-r1", "iqp-r1"], range(5), mapping="pca", nq=12)
    q2, c2 = _cells(["angle-r1", "iqp-r1"], range(5), mapping="selectk", nq=8)
    q3, c3 = _cells(["angle-r1", "iqp-r1"], range(1), mapping="randproj", nq=6)
    q_by.update(q2); q_by.update(q3)
    c_by.update(c2); c_by.update(c3)
    fam = tph.report_sweep("churn", q_by, c_by, list(range(5)))
    assert fam["cells_attempted"] == 3
    assert fam["cells_included"] == 2
    assert fam["cells_excluded"] == [["randproj", 6]]
    assert fam["holm_family_size"] == 2
    assert fam["bears_on_h1"] is False


def test_sweep_holm_values_belong_to_their_own_cell():
    """The printed table is sorted by mean; the structured levels are not.
    This is the pairing that a display-order zip would silently break."""
    q_by, c_by = {}, {}
    for mapping, nq in (("pca", 12), ("selectk", 8), ("randproj", 6)):
        a, b = _cells(["angle-r1", "iqp-r1"], range(7), mapping=mapping, nq=nq)
        q_by.update(a); c_by.update(b)
    fam = tph.report_sweep("churn", q_by, c_by, list(range(7)))
    assert fam["cells_included"] == 3
    expect = tph.holm([lv["p_wilcoxon"] for lv in fam["levels"]])
    assert [lv["p_holm"] for lv in fam["levels"]] == pytest.approx(expect)


def test_file_provenance_digests_what_it_read(tmp_path):
    import hashlib
    f = tmp_path / "x.jsonl"
    f.write_bytes(b'{"a": 1}\n')
    got = tph.file_provenance(f)
    assert got["present"] is True
    assert got["bytes"] == 9
    assert got["sha256"] == hashlib.sha256(b'{"a": 1}\n').hexdigest()
    assert tph.file_provenance(tmp_path / "absent.jsonl")["present"] is False
