from dataclasses import dataclass
from enum import Enum


class ResearchMode(str, Enum):
    DIRECT = "direct"
    FACT_SIMILARITY = "fact_similarity"
    LEGAL_SIMILARITY = "legal_similarity"
    CITATION = "citation"
    STATUTORY = "statutory"
    INVERSE = "inverse"
    ADVERSARIAL = "adversarial"
    PRECEDENT_ATTACK = "precedent_attack"


@dataclass
class RankingFactors:
    """Deterministic inputs to the authority score — never vector similarity alone (spec §9)."""

    jurisdiction_match: bool
    is_binding: bool
    court_level: int  # 0 = trial, higher = more senior appellate
    days_since_decision: int
    treatment_signal: float  # -1 (heavily criticised/overruled) .. +1 (heavily followed/approved)
    source_reliability: float  # 0..1, by source_type tier
    fact_similarity: float | None = None  # 0..1
    legal_similarity: float | None = None  # 0..1
    retrieval_score: float = 0.0  # kNN cosine similarity to the query — the actual relevance signal


# Weights per mode. Every weight vector sums to 1.0 across the factors it uses;
# fact/legal similarity default to 0 when the mode doesn't apply them.
#
# `retrieval` (the hybrid search's real semantic/keyword match to THIS query) is the
# only factor here that is actually query-dependent for a query with no fact/legal
# profile — everything else (jurisdiction_match, binding, court_level, treatment,
# reliability) is a static property of the document itself. It used to be weighted
# ~0.05 everywhere, which meant ranking was almost entirely by document metadata and
# barely by whether the document has anything to do with the question — verified live:
# every statute in a 5-document corpus scored ~0.70 for a completely unrelated query.
# `statutory_relevance` was a second, worse offender: it's hardcoded to 1.0 for any
# statute document regardless of topic, and since STATUTORY-mode queries already filter
# to doc_type in (statute, regulation), it was a constant 1.0 for 100% of candidates —
# a large (0.40) fixed bonus with zero discriminative power. It's dropped here.
_MODE_WEIGHTS: dict[ResearchMode, dict[str, float]] = {
    ResearchMode.DIRECT: {
        "jurisdiction_match": 0.10, "binding": 0.15, "court_level": 0.05, "recency": 0.05,
        "treatment": 0.15, "reliability": 0.05, "fact_sim": 0.05,
        "legal_sim": 0.10, "retrieval": 0.30,
    },
    ResearchMode.FACT_SIMILARITY: {
        "jurisdiction_match": 0.05, "binding": 0.05, "court_level": 0.05, "recency": 0.05,
        "treatment": 0.05, "reliability": 0.05, "fact_sim": 0.55,
        "legal_sim": 0.05, "retrieval": 0.10,
    },
    ResearchMode.LEGAL_SIMILARITY: {
        "jurisdiction_match": 0.05, "binding": 0.05, "court_level": 0.05, "recency": 0.05,
        "treatment": 0.05, "reliability": 0.05, "fact_sim": 0.05,
        "legal_sim": 0.45, "retrieval": 0.20,
    },
    ResearchMode.CITATION: {
        "jurisdiction_match": 0.05, "binding": 0.15, "court_level": 0.10, "recency": 0.05,
        "treatment": 0.30, "reliability": 0.05, "fact_sim": 0.00,
        "legal_sim": 0.05, "retrieval": 0.25,
    },
    ResearchMode.STATUTORY: {
        "jurisdiction_match": 0.15, "binding": 0.05, "court_level": 0.00, "recency": 0.05,
        "treatment": 0.05, "reliability": 0.10, "fact_sim": 0.00,
        "legal_sim": 0.00, "retrieval": 0.60,
    },
}
_MODE_WEIGHTS[ResearchMode.INVERSE] = _MODE_WEIGHTS[ResearchMode.DIRECT]
_MODE_WEIGHTS[ResearchMode.ADVERSARIAL] = _MODE_WEIGHTS[ResearchMode.DIRECT]
_MODE_WEIGHTS[ResearchMode.PRECEDENT_ATTACK] = _MODE_WEIGHTS[ResearchMode.CITATION]


def _recency_score(days_since_decision: int) -> float:
    """Newer authority scores higher, saturating past ~20 years — old good law isn't penalized hard."""
    years = max(days_since_decision, 0) / 365.0
    return max(0.0, 1.0 - min(years, 20.0) / 20.0)


def score_authority(factors: RankingFactors, mode: ResearchMode) -> float:
    weights = _MODE_WEIGHTS[mode]
    treatment_normalized = (factors.treatment_signal + 1.0) / 2.0
    court_level_normalized = min(factors.court_level / 4.0, 1.0)

    score = (
        weights["jurisdiction_match"] * (1.0 if factors.jurisdiction_match else 0.0)
        + weights["binding"] * (1.0 if factors.is_binding else 0.0)
        + weights["court_level"] * court_level_normalized
        + weights["recency"] * _recency_score(factors.days_since_decision)
        + weights["treatment"] * treatment_normalized
        + weights["reliability"] * factors.source_reliability
        + weights["fact_sim"] * (factors.fact_similarity or 0.0)
        + weights["legal_sim"] * (factors.legal_similarity or 0.0)
        + weights["retrieval"] * min(factors.retrieval_score, 1.0)
    )
    return round(score, 4)
