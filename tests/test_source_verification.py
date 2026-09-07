from types import SimpleNamespace

from agents.source_verification import verify_claim
from research.schemas import Claim, ClaimType, SourceRef


def _fake_section(section_id=1, document_id=10, text="The court held that liability attaches."):
    document = SimpleNamespace(
        id=document_id,
        title="Real Case v. Real Party",
        citation_string="123 F.3d 456",
        source_url="https://www.courtlistener.com/opinion/real-case/",
    )
    return SimpleNamespace(id=section_id, document_id=document_id, document=document, locator="¶12", text=text)


def _authority_claim(document_id=10, section_id=1, extract="something the model paraphrased, not verbatim"):
    return Claim(
        text="The proposition is supported.",
        claim_type=ClaimType.AUTHORITY,
        source=SourceRef(
            document_id=document_id,
            section_id=section_id,
            title="whatever the model wrote",
            citation_string=None,
            locator=None,
            extract=extract,
        ),
        confidence=1.0,
    )


def test_real_id_pair_verifies_even_if_extract_is_paraphrased():
    cache = {1: _fake_section()}
    claim = _authority_claim(extract="a paraphrase that does not match the stored text at all")

    result = verify_claim(claim, cache)

    assert result.verified is True
    assert result.claim_type == ClaimType.AUTHORITY


def test_verified_claim_source_is_rebuilt_from_the_db_not_the_llm():
    cache = {1: _fake_section()}
    claim = _authority_claim()

    result = verify_claim(claim, cache)

    assert result.source.title == "Real Case v. Real Party"
    assert result.source.citation_string == "123 F.3d 456"
    assert result.source.source_url == "https://www.courtlistener.com/opinion/real-case/"
    assert result.source.extract == "The court held that liability attaches."
    assert result.source.locator == "¶12"


def test_nonexistent_section_id_is_downgraded_and_stripped():
    cache = {1: _fake_section()}
    claim = _authority_claim(section_id=999)

    result = verify_claim(claim, cache)

    assert result.verified is False
    assert result.claim_type == ClaimType.UNRESOLVED
    assert result.source is None


def test_mismatched_document_id_for_a_real_section_is_rejected():
    cache = {1: _fake_section(document_id=10)}
    claim = _authority_claim(document_id=999, section_id=1)

    result = verify_claim(claim, cache)

    assert result.verified is False
    assert result.claim_type == ClaimType.UNRESOLVED


def test_non_authority_claims_pass_through_unchanged():
    claim = Claim(text="This is speculative.", claim_type=ClaimType.SPECULATION, source=None)

    result = verify_claim(claim, {})

    assert result == claim
