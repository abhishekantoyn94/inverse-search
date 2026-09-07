from ingestion.source_classification import classify_source_type
from knowledge.models import SourceType


def test_courtlistener_case_is_primary():
    assert classify_source_type("courtlistener", "case") == SourceType.PRIMARY


def test_govinfo_statute_is_primary():
    assert classify_source_type("govinfo", "statute") == SourceType.PRIMARY


def test_congress_gov_is_quasi_primary():
    assert classify_source_type("congress_gov", "secondary") == SourceType.QUASI_PRIMARY


def test_law_review_is_secondary():
    assert classify_source_type("law_review", "secondary") == SourceType.SECONDARY


def test_unknown_provider_defaults_to_discovery():
    assert classify_source_type("random_blog", "secondary") == SourceType.DISCOVERY
