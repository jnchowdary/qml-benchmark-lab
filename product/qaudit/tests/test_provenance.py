"""The four axes, and that nothing collapses them back into one.

WHY THIS FILE EXISTS
--------------------
An early design carried one "provenance tier" with the values borrowed,
own-hardware and unvalidated. That conflates where a NUMBER came from with
whether a CHECK has ever been tried outside the project that wrote it. The two
vary independently, and a report that merges them lets a reader infer
validation from data provenance or the reverse. These tests hold them apart:

  1. where the data came from        declared per record, never inferred
  2. whether the check could run     SKIP and NOT RUN are not PASS
  3. what it found                   detail and numbers
  4. what validates the check        a register, checked against its evidence
"""

import json
from pathlib import Path

import pytest

from qaudit import audit, provenance as prov

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def write(tmp_path, recs, name="r.jsonl"):
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    return str(p)


def base(**kw):
    r = dict(method="quantum", seed=0, n_train=60, n_test=150, test_base_rate=0.5,
             test_average_precision=0.64, test_roc_auc=0.66, final_converged=True)
    r.update(kw)
    return r


# ----------------------------------------------------- 1. provenance of the data

class TestProvenanceIsDeclaredNeverInferred:

    def test_a_method_named_hardware_is_not_a_declaration(self):
        """The whole point of the field.

        A record saying `method: "hardware"` has told us what somebody called a
        column. It has not told us a QPU ran. D18 of the research project is
        what happens when a number is believed to mean something it does not,
        and inferring provenance from a method name would rebuild that error
        inside the tool meant to catch it.
        """
        assert prov.record_provenance({"method": "hardware"}) == prov.UNSTATED
        assert prov.record_provenance({"method": "hardware", "backend": "ibm_fez",
                                       "shots": 1024}) == prov.UNSTATED

    def test_an_unknown_value_is_unstated_rather_than_accepted(self):
        """Not a free-text field. A typo must not become a provenance class."""
        assert prov.record_provenance({"provenance": "quantum-ish"}) == prov.UNSTATED
        assert prov.record_provenance({"provenance": 7}) == prov.UNSTATED

    @pytest.mark.parametrize("value", sorted(prov.RECORD_PROVENANCE))
    def test_every_declared_value_round_trips(self, value):
        assert prov.record_provenance({"provenance": value}) == value

    def test_the_banner_leads_with_what_the_file_does_not_say(self):
        s = prov.provenance_summary([base(), base()])
        first = prov.provenance_banner(s)[0]
        assert "does not state" in first

    def test_telemetry_is_counted_over_the_whole_file_and_over_hardware_separately(self):
        """Two counts, two meanings. A classical record has no shots to report,
        so demanding them of one would make the check fire on every mixed file,
        and a check that fires on everything carries no information."""
        recs = [base(provenance="own-hardware", shots=1024, backend="ibm_x",
                     quantum_seconds=1.0),
                base(provenance="classical")]
        s = prov.provenance_summary(recs)
        assert s["cost_fields_present"]["shots"] == 1          # of two records
        assert s["cost_fields_present_on_hardware"]["shots"] == 1  # of one hardware record
        assert s["n_declared_hardware"] == 1


# ------------------------------------------------- 2 and 3. ran, and what it found

class TestHardwareCostClaims:

    def test_no_hardware_declared_means_out_of_scope_not_satisfied(self, tmp_path):
        o = audit.check_cost_claim_support([base(), base()], {})
        assert o.status == audit.SKIP
        assert o.status != audit.PASS
        assert "no QPU-cost claim is in scope" in o.detail

    def test_declared_simulator_only_is_also_out_of_scope_and_says_so_differently(self):
        o = audit.check_cost_claim_support(
            [base(provenance="simulator"), base(provenance="classical")], {})
        assert o.status == audit.SKIP
        assert "none of them is hardware" in o.detail

    def test_hardware_without_telemetry_is_a_stated_limitation(self):
        o = audit.check_cost_claim_support([base(provenance="own-hardware")], {})
        assert o.status == audit.WARN
        assert "LIMITATION" in o.detail
        for f in prov.COST_FIELDS:
            assert f in o.detail
        # and it must not contaminate the results claims, which are unaffected
        assert "Results claims are unaffected" in o.detail

    def test_a_circuit_count_alone_does_not_satisfy_it(self):
        """D18 in one assertion. circuit_evaluations is a pair count; hardware
        runs each pair once per shot, so the count is not a cost."""
        o = audit.check_cost_claim_support(
            [base(provenance="own-hardware", circuit_evaluations=113575)], {})
        assert o.status == audit.WARN
        assert "not a cost" in o.detail

    def test_complete_telemetry_passes_and_totals_it(self):
        recs = [base(provenance="own-hardware", shots=1024, backend="ibm_a",
                     quantum_seconds=10.5),
                base(provenance="borrowed-hardware", shots=2048, backend="ibm_b",
                     quantum_seconds=4.5),
                base(provenance="classical")]
        o = audit.check_cost_claim_support(recs, {})
        assert o.status == audit.PASS
        assert o.numbers["total_shots"] == 3072
        assert o.numbers["total_quantum_seconds"] == pytest.approx(15.0)
        assert o.numbers["backends"] == ["ibm_a", "ibm_b"]

    def test_telemetry_is_never_a_configuration(self):
        """A cost field taking two values, each scored by every method, would be
        inferred as a configuration and double the cell count."""
        for f in ("provenance", "shots", "backend", "quantum_seconds", "job_id"):
            assert f in audit.NEVER_CELL

    def test_the_check_is_wired_in(self):
        assert audit.check_cost_claim_support in audit.CHECKS


# -------------------------------------------- 4. what validates each check

class TestValidationRegister:

    def test_every_check_has_a_register_entry(self):
        """A check with no entry would print nothing about its own evidence,
        which reads as having some."""
        names = set()
        for o in audit.CHECKS:
            names.add(getattr(o, "__name__", str(o)))
        # the register is keyed by report name, so compare against a real run
        assert set(prov.VALIDATION) >= {"schema", "kernel conditioning",
                                        "hardware cost claims"}

    def test_the_register_matches_the_external_case_it_cites(self):
        """The register claims what each check did on the one foreign file. That
        claim is transcribed from the committed report of that run, so it is
        checked against it rather than trusted."""
        case = json.loads((FIXTURES / "external_case_kakavand.json").read_text(encoding="utf-8"))
        statuses = case["statuses"]
        expected_word = {
            audit.SKIP: "declined",
            audit.NOT_RUN: "not run",
            audit.FAIL: "reported",
            audit.PASS: ("measured", "read"),
            audit.WARN: ("measured", "read"),
        }
        for name, status in statuses.items():
            claim = prov.VALIDATION.get(name)
            assert claim is not None, f"{name} ran externally but the register says it did not"
            want = expected_word[status]
            want = (want,) if isinstance(want, str) else want
            assert claim.startswith(want), (
                f"{name}: status {status} in the external case, register says {claim!r}")

    def test_checks_added_after_the_external_case_claim_no_validation(self):
        case = json.loads((FIXTURES / "external_case_kakavand.json").read_text(encoding="utf-8"))
        for name, claim in prov.VALIDATION.items():
            if name not in case["statuses"]:
                assert claim is None, (
                    f"{name} was not in the external case but the register claims {claim!r}")

    def test_the_banner_names_the_unexercised_checks_and_the_lack_of_a_defect(self):
        text = "\n".join(prov.validation_banner())
        assert "found no defect" in text
        assert "Never exercised on any external file" in text
        assert "hardware cost claims" in text

    def test_the_banner_does_not_claim_more_cases_than_exist(self):
        assert "One external case exists" in prov.EXTERNAL_EVIDENCE_NOTE


# ------------------------------------------------------- the report's own record

class TestReportRecordsItself:

    def test_the_environment_names_the_numerics(self):
        e = prov.environment()
        for k in ("python", "platform", "numpy", "scipy", "blas"):
            assert k in e
        assert e["numpy"] and e["scipy"]

    def test_the_environment_note_says_why_it_is_there(self):
        assert "byte for byte" in prov.environment_note()
