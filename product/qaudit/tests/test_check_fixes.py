"""Two defects found after the extraction, and the shipped template that found one.

Neither was caused by the extraction and neither shows on the one external file,
which fails on required fields and never reaches either code path. Both were
found by running the tool on its own template, which is the argument for
shipping a template that is exercised rather than described.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from qaudit import audit

PKG = Path(__file__).resolve().parents[1]
TEMPLATE = PKG / "template.jsonl"
CONTROL = PKG / "template_control.jsonl"


def write(tmp_path, recs, name="r.jsonl"):
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    return str(p)


def rec(**kw):
    r = dict(method="quantum", seed=0, n_train=60, n_test=150, test_base_rate=0.5,
             test_average_precision=0.64, test_roc_auc=0.66,
             test_label_fingerprint="abc", shuffled=False, final_converged=True)
    r.update(kw)
    return r


class TestSchemaDoesNotWarnAboutAPermittedAbsence:
    """`cell` was in the recommended-fields list and should not have been.

    Section 2 of the protocol says configuration may be supplied EITHER as a
    nested `cell` dict OR as top-level fields the audit infers. Warning about
    `cell` when the inference succeeded warned about an absence the protocol
    explicitly permits, and the shipped template took the documented second
    route and was warned for it.
    """

    def test_no_warning_when_configuration_was_inferred(self):
        recs = [rec(mapping="pca", n_qubits=12), rec(method="rbf", mapping="pca", n_qubits=12),
                rec(mapping="selectk", n_qubits=8), rec(method="rbf", mapping="selectk", n_qubits=8)]
        o = audit.check_schema(recs, {"cell_fields": ["mapping", "n_qubits"]})
        assert o.status == audit.PASS, o.detail
        assert "cell" not in o.detail

    def test_no_warning_when_a_nested_cell_dict_was_supplied(self):
        recs = [rec(cell={"mapping": "pca"}), rec(cell={"mapping": "pca"})]
        o = audit.check_schema(recs, {"cell_fields": []})
        assert o.status == audit.PASS, o.detail

    def test_warns_when_neither_route_exists(self):
        """A file with no configuration at all IS missing something, and the
        warning must name both routes so the reader knows either will do."""
        o = audit.check_schema([rec(), rec()], {"cell_fields": []})
        assert o.status == audit.WARN
        assert "cell" in o.detail and "inferred" in o.detail

    def test_the_other_recommended_fields_still_warn(self):
        o = audit.check_schema([rec(mapping="pca")], {"cell_fields": ["mapping"]})
        o2 = audit.check_schema(
            [{k: v for k, v in rec(mapping="pca").items() if k != "shuffled"}],
            {"cell_fields": ["mapping"]})
        assert o.status == audit.PASS
        assert o2.status == audit.WARN and "shuffled" in o2.detail


class TestNegativeControlDoesNotPrintAMeaninglessSigma:
    """The verdict rule always required both a sigma bar and the floor. The PASS
    line printed the sigma regardless, and on a healthy control that is the
    common case: a control sitting at its null has almost no spread across
    splits by construction. The first run of the shipped template printed
    -479279874081.53 sigma on a PASS.
    """

    def _ctrl(self, pairs):
        """pairs: (seed, ap, roc) rows."""
        return [rec(seed=s, shuffled=True, test_average_precision=ap, test_roc_auc=roc)
                for s, ap, roc in pairs]

    def test_sigma_is_suppressed_when_the_deviation_is_inside_the_floor(self):
        ctrl = self._ctrl([(0, 0.5150, 0.4998), (1, 0.5158, 0.5002),
                           (2, 0.5152, 0.4999), (3, 0.5156, 0.5001)])
        o = audit.check_negative_control([rec()], {"control": ctrl, "floor": 1e-3})
        assert o.status == audit.PASS
        assert "sigma)" not in o.detail
        assert "within the 0.001 floor" in o.detail
        assert "floating-point residue" in o.detail
        for label in ("ROC-AUC", "normAP"):
            assert o.numbers[label]["sigma_reportable"] is False

    def test_sigma_is_given_when_the_deviation_clears_the_floor(self):
        ctrl = self._ctrl([(0, 0.5300, 0.5400), (1, 0.5320, 0.5380),
                           (2, 0.5310, 0.5390), (3, 0.5290, 0.5410)])
        o = audit.check_negative_control([rec()], {"control": ctrl, "floor": 1e-3})
        assert o.numbers["ROC-AUC"]["sigma_reportable"] is True
        assert "sigma" in o.detail

    def test_a_real_leak_still_fails(self):
        """The display change must not soften the verdict."""
        ctrl = self._ctrl([(0, 0.80, 0.85), (1, 0.81, 0.86),
                           (2, 0.79, 0.84), (3, 0.82, 0.87)])
        o = audit.check_negative_control([rec()], {"control": ctrl, "floor": 1e-3})
        assert o.status == audit.FAIL
        assert "Investigate" in o.detail

    def test_the_null_is_recorded_so_the_reader_need_not_know_it(self):
        ctrl = self._ctrl([(0, 0.5150, 0.4998), (1, 0.5158, 0.5002)])
        o = audit.check_negative_control([rec()], {"control": ctrl, "floor": 1e-3})
        assert o.numbers["ROC-AUC"]["null"] == 0.5
        assert o.numbers["normAP"]["null"] == 0.0


class TestTheShippedTemplateIsExercised:
    """A template a user copies must be run, not described. Both defects above
    were found by running the tool on it, and the first draft of it had four
    mistakes of its own: the selected hyperparameters were encoded into the
    method name, which gave five methods and broke configuration inference, and
    the control's labels were permuted on one endpoint and not the other.
    """

    def test_both_files_are_present_and_readable(self):
        for p in (TEMPLATE, CONTROL):
            recs = audit.load(str(p))
            assert len(recs) == 8, p.name

    def test_the_template_carries_every_required_and_recommended_field(self):
        recs = audit.load(str(TEMPLATE))
        for f in ("method", "seed", "n_train", "n_test", "test_base_rate",
                  "test_average_precision", "test_roc_auc",
                  "test_label_fingerprint", "shuffled", "final_converged",
                  "inner_score", "params"):
            assert audit.has(recs, f), f

    def test_the_configuration_is_inferable_from_top_level_fields(self):
        """The documented alternative to a nested `cell` dict. If the method
        names ever encode the setting again, this fails."""
        recs = audit.load(str(TEMPLATE))
        assert audit.infer_cell_fields(recs) == ["mapping", "n_qubits"]
        assert sorted({r["method"] for r in recs}) == ["quantum", "rbf"]

    def test_the_control_is_permuted_on_both_endpoints(self):
        """Permuting one and leaving the other at its real value is what made
        the first draft return FAIL at +45 sigma on the untouched endpoint."""
        recs = audit.load(str(CONTROL))
        assert all(r["shuffled"] for r in recs)
        import statistics as st
        assert abs(st.mean(r["test_roc_auc"] for r in recs) - 0.5) < 0.01
        assert abs(st.mean(r["test_average_precision"] for r in recs) - 0.5154) < 0.01

    def test_the_hardware_arm_can_support_a_cost_claim(self):
        recs = audit.load(str(TEMPLATE))
        o = audit.check_cost_claim_support(recs, {})
        assert o.status == audit.PASS
        assert o.numbers["total_shots"] == 4096

    def test_the_whole_template_runs_through_the_cli(self):
        proc = subprocess.run(
            [sys.executable, "-m", "qaudit.audit", str(TEMPLATE), "--control", str(CONTROL)],
            capture_output=True, text=True)
        assert proc.returncode == 1, proc.stdout[-2000:] + proc.stderr[-2000:]
        out = proc.stdout
        assert "Configuration grouped by: mapping, n_qubits" in out
        assert "[ PASS  ] schema" in out
        assert "[ PASS  ] negative control" in out
        assert "[ PASS  ] tuning symmetry" in out
        assert "[ PASS  ] hardware cost claims" in out
        assert "0 failed" in out
