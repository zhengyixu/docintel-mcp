from conftest import sample

from docintel.extractors.rules import RulesExtractor
from docintel.pipeline import document_id_for, process
from docintel.schemas import DocType


def run(name: str):
    return process(name, sample(name), RulesExtractor())


def test_clean_coi_is_accepted():
    result = run("coi_001.txt")
    assert result.doc_type is DocType.COI
    assert result.status == "accepted"
    assert result.issues == []
    assert result.data["policy_number"] == "CGL-00482917"
    assert result.data["each_occurrence_limit"] == "1000000"
    assert result.data["policy_expiration"] == "2027-07-01"


def test_messy_coi_needs_review():
    result = run("coi_002_messy.txt")
    assert result.status == "needs_review"
    low = {f.name for f in result.low_confidence_fields()}
    # Found through looser aliases, or missing altogether: a human should look.
    assert {"insured_name", "policy_number", "certificate_holder"} <= low
    assert any(i.rule == "policy_number_format" for i in result.issues)


def test_clean_loss_run_is_accepted():
    result = run("loss_run_001.txt")
    assert result.doc_type is DocType.LOSS_RUN
    assert result.status == "accepted"
    assert len(result.data["claims"]) == 3
    assert result.data["total_incurred"] == "145740.50"


def test_loss_run_with_wrong_total_is_caught_by_rules():
    result = run("loss_run_002_bad_total.txt")
    assert result.status == "needs_review"
    assert [i.rule for i in result.issues] == ["loss_run_total"]


def test_unparseable_document_is_rejected():
    result = process("junk.txt", "nothing useful here", RulesExtractor())
    assert result.status == "rejected"
    assert result.data is None
    assert all(i.rule == "schema" for i in result.issues)


def test_document_id_is_stable_for_the_same_content():
    text = sample("coi_001.txt")
    assert document_id_for(text) == document_id_for(text)
    assert document_id_for(text) != document_id_for(text + " ")
