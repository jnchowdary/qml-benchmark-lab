"""The aggregation and exclusion rules in `exploratory_sweep.py`.

WHY THIS FILE EXISTS
--------------------
Two mechanisms in that script exist only to prevent defects this project has
already made and recorded. Untested, either can regress silently.

**1. Pseudo-replication across cells.** Week 4 item 10:

    "A trend statistic on the wrong unit. `trend_stats` correlated over all 300
     records rather than the 15 cells, treating twenty seeds of one
     configuration as twenty independent observations of a trend across cells.
     It returned fraud `angle-r2` at rho -0.149 with p = 0.0099 on a column
     where every gap sat at or below D2's 1e-3 precision floor. The cell-level
     figures, n = 15, are the ones this record reports; every row-level figure
     printed before the fix is void."

The same hazard applies to the qubit-count and per-mapping families: at one
qubit count the three mappings share a train/test split, because `make_split`
is keyed on the seed alone. `seed_means` averages within each seed before any
test, so a level carries 20 paired observations and not 60 pooled rows. The
cell-level trend is separately pinned to n = 15.

**2. A registered exclusion kept in code rather than in memory.**
Pre-registration line 104: the 50-per-class arm "is run for the shape of the
learning curve and is **not** used for hypothesis testing". If that exclusion
drifts, an underpowered arm enters a Holm family and changes every corrected
p-value in it.

**3. The NaN class.** `scipy.stats.spearmanr` returns NaN on constant input and
every comparison against NaN is False, which in this project has twice turned a
non-result into a printed verdict. The trend must report an undefined
correlation as undefined.

Every case below is constructed so that the wrong implementation gives a
visibly different answer, not merely a different number.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import exploratory_sweep as es  # noqa: E402
from primary_tests import holm  # noqa: E402


def diffs_for(cells, seeds, value):
    """{(mapping, qubits): {seed: (d_normap, d_roc)}} with value(cell, seed)."""
    return {c: {s: value(c, s) for s in seeds} for c in cells}


# ------------------------------------------------- seed_means: the pairing rule

class TestSeedMeans:

    def test_returns_one_value_per_seed_not_one_per_row(self):
        """Three cells, twenty seeds. A pooling implementation returns 60."""
        seeds = list(range(20))
        cells = [("pca", 8), ("randproj", 8), ("selectk", 8)]
        d = diffs_for(cells, seeds, lambda c, s: (1.0, 2.0))
        got = es.seed_means(d, cells, seeds)
        assert len(got) == 20, f"expected 20 paired observations, got {len(got)}"

    def test_each_value_is_the_within_seed_mean_across_cells(self):
        seeds = [0, 1]
        cells = [("pca", 8), ("randproj", 8), ("selectk", 8)]
        # seed 0 -> 0.0, 0.3, 0.6 (mean 0.3); seed 1 -> 1.0, 1.3, 1.6 (mean 1.3)
        table = {(("pca", 8), 0): 0.0, (("randproj", 8), 0): 0.3,
                 (("selectk", 8), 0): 0.6, (("pca", 8), 1): 1.0,
                 (("randproj", 8), 1): 1.3, (("selectk", 8), 1): 1.6}
        d = diffs_for(cells, seeds, lambda c, s: (table[(c, s)], 0.0))
        got = es.seed_means(d, cells, seeds)
        assert got == pytest.approx([0.3, 1.3])

    def test_idx_selects_the_roc_endpoint(self):
        seeds = [0]
        cells = [("pca", 8)]
        d = diffs_for(cells, seeds, lambda c, s: (0.1, 0.9))
        assert es.seed_means(d, cells, seeds, idx=0) == pytest.approx([0.1])
        assert es.seed_means(d, cells, seeds, idx=1) == pytest.approx([0.9])

    def test_a_missing_cell_is_skipped_and_nothing_is_invented(self):
        """Two of three cells present. The seed still yields one value, the
        mean of what exists, and no placeholder enters the series."""
        seeds = [0]
        present = [("pca", 8), ("randproj", 8)]
        d = diffs_for(present, seeds, lambda c, s: (1.0, 0.0))
        asked = present + [("selectk", 8)]
        got = es.seed_means(d, asked, seeds)
        assert got == pytest.approx([1.0])

    def test_a_seed_absent_everywhere_contributes_nothing(self):
        seeds = [0, 1, 2]
        cells = [("pca", 8)]
        d = {("pca", 8): {0: (1.0, 0.0), 2: (3.0, 0.0)}}  # seed 1 missing
        got = es.seed_means(d, cells, seeds)
        assert got == pytest.approx([1.0, 3.0])


# ------------------------------------------- tested_family: Holm within family

class TestTestedFamily:

    def test_holm_is_applied_within_the_family(self):
        series = {"a": [0.5] * 12, "b": [0.4] * 12, "c": [-0.3] * 12}
        fam = es.tested_family("f", ["a", "b", "c"], series, "note")
        raw = [r["p_wilcoxon"] for r in fam["rows"] if r["estimable"]]
        adj = [r["p_holm"] for r in fam["rows"] if r["estimable"]]
        assert adj == pytest.approx(holm(raw))

    def test_caption_reports_the_family_size_and_says_exploratory(self):
        series = {"a": [0.5] * 12, "b": [0.4] * 12}
        fam = es.tested_family("f", ["a", "b"], series, "note")
        assert "EXPLORATORY" in fam["caption"]
        assert "family of 2" in fam["caption"]
        assert "no confirmatory hypothesis" in fam["caption"]

    def test_a_level_with_too_few_observations_is_not_estimable(self):
        """One observation cannot be tested. It must be marked, not tested, and
        must not consume a Holm slot and inflate the others."""
        series = {"a": [0.5] * 12, "thin": [0.5]}
        fam = es.tested_family("f", ["a", "thin"], series, "note")
        thin = next(r for r in fam["rows"] if r["level"] == "thin")
        assert thin["estimable"] is False
        assert "p_holm" not in thin
        assert "family of 1" in fam["caption"]

    def test_aggregation_note_is_carried_into_the_output(self):
        fam = es.tested_family("f", ["a"], {"a": [0.1] * 12}, "THE NOTE")
        assert fam["aggregation"] == "THE NOTE"


# --------------------------------------- the registered n=50 testing exclusion

class TestTrainingSizeExclusion:

    @staticmethod
    def _by_size():
        seeds = list(range(20))
        cells = [(m, q) for m in es.MAPPINGS for q in es.QUBITS]
        by_size, seeds_by_size = {}, {}
        for n in es.SIZES:
            by_size[n] = diffs_for(cells, seeds, lambda c, s: (0.05, 0.01))
            seeds_by_size[n] = seeds
        return by_size, seeds_by_size

    def test_fifty_per_class_is_not_tested(self):
        fam = es.family_training_size(*self._by_size())
        tested = [r["level"] for r in fam["rows"]]
        assert 50 not in tested, "the 50-per-class arm entered a Holm family"
        assert sorted(tested) == [100, 250]

    def test_fifty_per_class_is_still_reported_with_its_reason(self):
        fam = es.family_training_size(*self._by_size())
        desc = fam["descriptive_only"]
        assert [r["level"] for r in desc] == [50]
        assert "line 104" in desc[0]["why_not_tested"]
        assert desc[0]["mean_d_normap"] is not None

    def test_the_exclusion_list_is_the_registered_one(self):
        assert es.NO_TEST_SIZES == (50,)

    def test_descriptive_rows_carry_the_d2_floor_flag(self):
        """D2 applies to a descriptive figure as much as to a tested one.

        Until 15 October 2026 the descriptive rows carried no below_d2_floor, so
        a mean under the pipeline's resolution would have printed as a bare
        number. No real row has ever been below the floor, so the gap was latent;
        this pins it shut in both directions.
        """
        above = es.family_training_size(*self._by_size())
        d = above["descriptive_only"][0]
        assert "below_d2_floor" in d
        assert d["below_d2_floor"] is False, "0.05 is above a 1e-3 floor"
        assert above["n_descriptive_below_floor"] == 0

        seeds = list(range(20))
        cells = [(m, q) for m in es.MAPPINGS for q in es.QUBITS]
        tiny = es.FLOOR / 10.0
        by_size, seeds_by_size = {}, {}
        for n in es.SIZES:
            by_size[n] = diffs_for(cells, seeds, lambda c, s: (tiny, tiny))
            seeds_by_size[n] = seeds
        below = es.family_training_size(by_size, seeds_by_size)
        d = below["descriptive_only"][0]
        assert d["below_d2_floor"] is True, (es.FLOOR, d["mean_d_normap"])
        assert below["n_descriptive_below_floor"] == 1

    def test_the_two_floor_counters_are_not_the_same_number(self):
        """n_levels_below_floor counts the TESTED rows because it describes the
        Holm family; n_descriptive_below_floor counts the excluded ones. Folding
        them together would let a descriptive figure inflate a count a reader
        reads as being about the family."""
        fam = es.family_training_size(*self._by_size())
        assert "n_levels_below_floor" in fam
        assert "n_descriptive_below_floor" in fam
        assert len(fam["rows"]) == 2 and len(fam["descriptive_only"]) == 1


# ----------------------------------- the cell-level trend unit, week 4 item 10

class TestQubitTrendUnit:

    @staticmethod
    def _full():
        seeds = list(range(20))
        cells = [(m, q) for m in es.MAPPINGS for q in es.QUBITS]
        # A monotone trend in qubit count, so the correlation is well defined.
        d = diffs_for(cells, seeds, lambda c, s: (0.01 * c[1], 0.0))
        return d, seeds

    def test_trend_unit_is_the_cell_and_n_is_fifteen(self):
        d, seeds = self._full()
        fam = es.family_qubit_trend(d, seeds)
        t = fam["cell_level_trend"]
        assert t["unit"] == "cell"
        assert t["n_cells"] == 15, (
            f"trend computed on {t['n_cells']} units; week 4 item 10 voided "
            f"every row-level trend figure in this project")

    def test_the_tested_family_has_one_level_per_qubit_count(self):
        d, seeds = self._full()
        fam = es.family_qubit_trend(d, seeds)
        assert [r["level"] for r in fam["rows"]] == list(es.QUBITS)
        for r in fam["rows"]:
            assert r["n"] == 20, (
                f"level {r['level']} carries {r['n']} observations; three "
                f"mappings at one seed share a split and must be averaged")

    def test_constant_input_gives_an_undefined_correlation_not_nan(self):
        """scipy returns NaN here and every NaN comparison is False, which is
        how this project twice printed a verdict where none existed."""
        seeds = list(range(20))
        cells = [(m, q) for m in es.MAPPINGS for q in es.QUBITS]
        d = diffs_for(cells, seeds, lambda c, s: (0.5, 0.0))  # flat
        fam = es.family_qubit_trend(d, seeds)
        t = fam["cell_level_trend"]
        assert t["spearman_rho"] is None
        assert t["p"] is None
        assert "undefined" in t["note"]


# ------------------------------------------------ per-mapping family structure

class TestPerMapping:

    def test_one_level_per_mapping_each_with_twenty_observations(self):
        seeds = list(range(20))
        cells = [(m, q) for m in es.MAPPINGS for q in es.QUBITS]
        d = diffs_for(cells, seeds, lambda c, s: (0.02, 0.0))
        fam = es.family_per_mapping(d, seeds)
        assert [r["level"] for r in fam["rows"]] == list(es.MAPPINGS)
        for r in fam["rows"]:
            assert r["n"] == 20, (
                f"mapping {r['level']} carries {r['n']} observations; the five "
                f"qubit counts at one seed share a split")
