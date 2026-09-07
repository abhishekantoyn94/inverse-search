import math
from dataclasses import dataclass, field

from pydantic import BaseModel

from retrieval.embeddings import embed


class FactProfile(BaseModel):
    """Structured facts extracted by an LLM (agentic step) from a query or a candidate case.

    The extraction is agentic; everything downstream in this module is deterministic.
    """

    parties: list[str] = []
    relationship: str | None = None
    conduct: str | None = None
    timeline: str | None = None
    transaction: str | None = None
    industry: str | None = None
    harm: str | None = None
    intent: str | None = None
    procedural_posture: str | None = None
    remedy: str | None = None
    narrative: str = ""


class LegalProfile(BaseModel):
    issue: str | None = None
    doctrine: str | None = None
    statutory_provision: str | None = None
    legal_test: str | None = None
    reasoning: str | None = None
    ratio: str | None = None
    interpretive_methodology: str | None = None
    narrative: str = ""


@dataclass
class SimilarityResult:
    score: float  # 0..1
    explanation: str
    matched_fields: list[str] = field(default_factory=list)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _field_overlap(fields_a: dict[str, str | None], fields_b: dict[str, str | None]) -> tuple[float, list[str]]:
    matched = []
    comparable = [k for k in fields_a if fields_a[k] and fields_b.get(k)]
    if not comparable:
        return 0.0, matched
    hits = 0
    for key in comparable:
        tokens_a = set(fields_a[key].lower().split())
        tokens_b = set(fields_b[key].lower().split())
        if tokens_a and tokens_b:
            jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
            if jaccard > 0.2:
                hits += 1
                matched.append(key)
    return hits / len(comparable), matched


def score_fact_similarity(query: FactProfile, candidate: FactProfile) -> SimilarityResult:
    field_score, matched = _field_overlap(
        {
            "relationship": query.relationship,
            "conduct": query.conduct,
            "timeline": query.timeline,
            "transaction": query.transaction,
            "industry": query.industry,
            "harm": query.harm,
            "intent": query.intent,
            "procedural_posture": query.procedural_posture,
            "remedy": query.remedy,
        },
        {
            "relationship": candidate.relationship,
            "conduct": candidate.conduct,
            "timeline": candidate.timeline,
            "transaction": candidate.transaction,
            "industry": candidate.industry,
            "harm": candidate.harm,
            "intent": candidate.intent,
            "procedural_posture": candidate.procedural_posture,
            "remedy": candidate.remedy,
        },
    )
    narrative_score = 0.0
    if query.narrative and candidate.narrative:
        narrative_score = _cosine(embed(query.narrative), embed(candidate.narrative))

    score = round(0.6 * field_score + 0.4 * max(narrative_score, 0.0), 4)
    explanation = (
        f"Matched material facts: {', '.join(matched) or 'none'}; "
        f"narrative similarity {narrative_score:.2f}."
    )
    return SimilarityResult(score=score, explanation=explanation, matched_fields=matched)


def score_legal_similarity(query: LegalProfile, candidate: LegalProfile) -> SimilarityResult:
    field_score, matched = _field_overlap(
        {
            "issue": query.issue,
            "doctrine": query.doctrine,
            "statutory_provision": query.statutory_provision,
            "legal_test": query.legal_test,
            "reasoning": query.reasoning,
            "ratio": query.ratio,
            "interpretive_methodology": query.interpretive_methodology,
        },
        {
            "issue": candidate.issue,
            "doctrine": candidate.doctrine,
            "statutory_provision": candidate.statutory_provision,
            "legal_test": candidate.legal_test,
            "reasoning": candidate.reasoning,
            "ratio": candidate.ratio,
            "interpretive_methodology": candidate.interpretive_methodology,
        },
    )
    narrative_score = 0.0
    if query.narrative and candidate.narrative:
        narrative_score = _cosine(embed(query.narrative), embed(candidate.narrative))

    score = round(0.6 * field_score + 0.4 * max(narrative_score, 0.0), 4)
    explanation = (
        f"Matched legal elements: {', '.join(matched) or 'none'}; "
        f"doctrinal narrative similarity {narrative_score:.2f}."
    )
    return SimilarityResult(score=score, explanation=explanation, matched_fields=matched)
