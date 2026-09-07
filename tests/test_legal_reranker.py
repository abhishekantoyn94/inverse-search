from ranking.legal_reranker import RankingFactors, ResearchMode, score_authority


def _base_factors(**overrides) -> RankingFactors:
    defaults = dict(
        jurisdiction_match=True,
        is_binding=True,
        court_level=4,
        days_since_decision=365,
        treatment_signal=0.5,
        source_reliability=1.0,
        retrieval_score=0.8,
    )
    defaults.update(overrides)
    return RankingFactors(**defaults)


def test_binding_outranks_persuasive_in_direct_mode():
    binding = score_authority(_base_factors(is_binding=True), ResearchMode.DIRECT)
    persuasive = score_authority(_base_factors(is_binding=False), ResearchMode.DIRECT)
    assert binding > persuasive


def test_negative_treatment_lowers_score():
    followed = score_authority(_base_factors(treatment_signal=1.0), ResearchMode.CITATION)
    overruled = score_authority(_base_factors(treatment_signal=-1.0), ResearchMode.CITATION)
    assert followed > overruled


def test_fact_similarity_dominates_fact_similarity_mode():
    high_fact_sim = score_authority(
        _base_factors(fact_similarity=0.95, legal_similarity=0.1), ResearchMode.FACT_SIMILARITY
    )
    low_fact_sim = score_authority(
        _base_factors(fact_similarity=0.1, legal_similarity=0.95), ResearchMode.FACT_SIMILARITY
    )
    assert high_fact_sim > low_fact_sim


def test_legal_similarity_dominates_legal_similarity_mode():
    high_legal_sim = score_authority(
        _base_factors(fact_similarity=0.1, legal_similarity=0.95), ResearchMode.LEGAL_SIMILARITY
    )
    low_legal_sim = score_authority(
        _base_factors(fact_similarity=0.95, legal_similarity=0.1), ResearchMode.LEGAL_SIMILARITY
    )
    assert high_legal_sim > low_legal_sim


def test_score_is_bounded():
    score = score_authority(_base_factors(), ResearchMode.DIRECT)
    assert 0.0 <= score <= 1.0


def test_retrieval_relevance_meaningfully_affects_statutory_score():
    # Regression test: statutory_relevance used to be hardcoded to 1.0 for any statute
    # document and dominated the STATUTORY score (0.40 weight), while the only actually
    # query-dependent signal (retrieval_score) carried just 0.05 — every statute in a
    # small corpus scored ~identically regardless of real topical relevance (verified
    # live). retrieval_score must now be the dominant factor for this mode.
    relevant = score_authority(_base_factors(retrieval_score=0.9), ResearchMode.STATUTORY)
    irrelevant = score_authority(_base_factors(retrieval_score=0.1), ResearchMode.STATUTORY)
    assert relevant - irrelevant > 0.3
