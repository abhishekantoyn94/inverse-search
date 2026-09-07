from ingestion.citation_extraction import extract_citations


def test_extracts_case_citation():
    citations = extract_citations("The court in Brown v. Board of Education, 347 U.S. 483 (1954), held that...")
    case_citations = [c for c in citations if c.citation_type == "case"]
    assert len(case_citations) == 1
    assert case_citations[0].reporter == "U.S."
    assert case_citations[0].page == "483"


def test_extracts_law_citation_without_crashing():
    # Regression test: FullLawCitation has no top-level .reporter attribute — the
    # reporter/title/section live in .groups. This used to raise AttributeError.
    citations = extract_citations("A conspiracy claim may arise under 42 U.S.C. § 1985(3) for deprivation of rights.")
    statute_citations = [c for c in citations if c.citation_type == "statute"]
    assert len(statute_citations) == 1
    assert statute_citations[0].reporter == "U.S.C."
    assert statute_citations[0].volume == "42"
    assert statute_citations[0].page == "1985"


def test_extracts_nothing_from_plain_text():
    assert extract_citations("This paragraph contains no legal citations at all.") == []
