from ranking.similarity import FactProfile, LegalProfile, score_fact_similarity, score_legal_similarity


def test_fact_similarity_matches_overlapping_fields():
    query = FactProfile(conduct="breach of contract for late delivery", industry="construction")
    candidate = FactProfile(conduct="breach of contract for late delivery", industry="construction")
    result = score_fact_similarity(query, candidate)
    assert result.score > 0
    assert "conduct" in result.matched_fields
    assert "industry" in result.matched_fields


def test_fact_similarity_zero_when_no_overlap():
    query = FactProfile(conduct="breach of contract", industry="construction")
    candidate = FactProfile(conduct="assault and battery", industry="hospitality")
    result = score_fact_similarity(query, candidate)
    assert result.score == 0.0
    assert result.matched_fields == []


def test_legal_similarity_matches_overlapping_doctrine():
    query = LegalProfile(doctrine="promissory estoppel", legal_test="reasonable reliance test")
    candidate = LegalProfile(doctrine="promissory estoppel", legal_test="reasonable reliance test")
    result = score_legal_similarity(query, candidate)
    assert result.score > 0
    assert "doctrine" in result.matched_fields


def test_no_fields_to_compare_yields_zero_score():
    result = score_fact_similarity(FactProfile(), FactProfile())
    assert result.score == 0.0
