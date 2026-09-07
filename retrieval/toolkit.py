"""The Retrieval Toolkit: the only way agents touch the corpus.

Agents never see raw prose they could hallucinate citations from — every function
here returns structured, source-pointed objects (document id, section id, locator,
exact extract) that a Claim can point straight at for the Source Verification gate.
"""

from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select

from knowledge.db import SessionLocal
from knowledge.models import Citation, Court, Document, DocumentSection, Jurisdiction
from ranking.legal_reranker import RankingFactors, ResearchMode, score_authority
from ranking.similarity import FactProfile, LegalProfile, score_fact_similarity, score_legal_similarity
from retrieval.hybrid_search import MetadataFilter, SectionHit, hybrid_search


@dataclass
class AuthorityResult:
    document_id: int
    section_id: int
    title: str
    citation_string: str | None
    court_name: str | None
    jurisdiction_name: str | None
    date_decided_or_enacted: date | None
    source_type: str
    doc_type: str
    locator: str | None
    extract: str
    source_url: str | None
    is_binding: bool
    authority_score: float
    fact_similarity: float | None = None
    fact_similarity_explanation: str | None = None
    legal_similarity: float | None = None
    legal_similarity_explanation: str | None = None
    treatment_summary: dict[str, int] = field(default_factory=dict)


def _treatment_signal(treatment_counts: dict[str, int]) -> float:
    positive = treatment_counts.get("follows", 0) + treatment_counts.get("approves", 0) + treatment_counts.get("applies", 0)
    negative = (
        treatment_counts.get("overrules", 0)
        + treatment_counts.get("criticises", 0)
        + treatment_counts.get("departs_from", 0)
        + treatment_counts.get("distinguishes", 0)
        + treatment_counts.get("narrows", 0)
    )
    total = positive + negative
    if total == 0:
        return 0.0
    return (positive - negative) / total


def _document_context(document_id: int) -> tuple[Document | None, Court | None, Jurisdiction | None, dict[str, int]]:
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is None:
            return None, None, None, {}
        court = session.get(Court, document.court_id) if document.court_id else None
        jurisdiction = session.get(Jurisdiction, document.jurisdiction_id) if document.jurisdiction_id else None

        treatment_counts: dict[str, int] = {}
        rows = session.scalars(select(Citation).where(Citation.cited_document_id == document_id))
        for row in rows:
            treatment_counts[row.treatment_type.value] = treatment_counts.get(row.treatment_type.value, 0) + 1

        return document, court, jurisdiction, treatment_counts


def _is_binding(court: Court | None, target_jurisdiction: str | None) -> bool:
    if court is None or target_jurisdiction is None:
        return False
    return court.binding_scope.get("jurisdictions", []) and target_jurisdiction in court.binding_scope.get(
        "jurisdictions", []
    )


# Below this raw kNN cosine similarity, a "match" is noise, not a real candidate —
# in a small corpus, hybrid_search always returns its top-k *something*, and an LLM
# shown a weak candidate directly will often rationalize it into apparent relevance
# rather than say "none of these apply" (verified live: a civil-rights statute was
# cited as "governing" a software-liability question). Calibrated from three live
# queries against this project's current small corpus: genuinely unrelated text
# topped out around 0.54-0.58, genuinely on-topic text ranged 0.62-0.73 depending on
# phrasing. This is a small-sample stopgap, not a rigorously calibrated constant —
# revisit it (ideally make it relative to the score distribution of a much larger,
# more diverse corpus) once one exists; three data points is not a lot to hang a
# hardcoded cutoff on.
MIN_RETRIEVAL_RELEVANCE = 0.60


def search_authorities(
    query_text: str,
    mode: ResearchMode,
    filters: MetadataFilter | None = None,
    target_jurisdiction: str | None = None,
    fact_profile: FactProfile | None = None,
    legal_profile: LegalProfile | None = None,
    top_k: int = 15,
) -> list[AuthorityResult]:
    hits: list[SectionHit] = hybrid_search(query_text, filters=filters, top_k=top_k * 2)

    results: list[AuthorityResult] = []
    for hit in hits:
        document, court, jurisdiction, treatment_counts = _document_context(hit.document_id)
        if document is None:
            continue

        # Fact/legal-similarity modes have their own relevance signal (structured
        # field overlap, not raw embedding distance) — the floor only applies where
        # the only relevance signal is the paragraph's overall semantic similarity.
        if fact_profile is None and legal_profile is None and hit.knn_score < MIN_RETRIEVAL_RELEVANCE:
            continue

        fact_sim_result = None
        legal_sim_result = None
        if fact_profile is not None:
            candidate_facts = FactProfile(narrative=hit.text)
            fact_sim_result = score_fact_similarity(fact_profile, candidate_facts)
        if legal_profile is not None:
            candidate_legal = LegalProfile(narrative=hit.text)
            legal_sim_result = score_legal_similarity(legal_profile, candidate_legal)

        jurisdiction_match = target_jurisdiction is not None and jurisdiction is not None and jurisdiction.name == target_jurisdiction
        is_binding = _is_binding(court, target_jurisdiction)
        days_since = (datetime.utcnow().date() - document.date_decided_or_enacted).days if document.date_decided_or_enacted else 3650

        factors = RankingFactors(
            jurisdiction_match=jurisdiction_match,
            is_binding=is_binding,
            court_level=court.level if court else 0,
            days_since_decision=days_since,
            treatment_signal=_treatment_signal(treatment_counts),
            source_reliability={"primary": 1.0, "quasi_primary": 0.8, "secondary": 0.5, "discovery": 0.2}[
                document.source_type.value
            ],
            fact_similarity=fact_sim_result.score if fact_sim_result else None,
            legal_similarity=legal_sim_result.score if legal_sim_result else None,
            # The raw kNN cosine similarity, not the RRF-fused rank score — RRF scores
            # are tiny (k=60 means well under 0.05) and barely vary between a great
            # match and an unrelated one, which is how an irrelevant document could
            # score as "relevant" as a genuine match (verified live). Cosine similarity
            # is a meaningful 0..1-ish signal that actually reflects semantic closeness.
            retrieval_score=hit.knn_score,
        )

        results.append(
            AuthorityResult(
                document_id=document.id,
                section_id=hit.section_id,
                title=document.title,
                citation_string=document.citation_string,
                court_name=court.name if court else None,
                jurisdiction_name=jurisdiction.name if jurisdiction else None,
                date_decided_or_enacted=document.date_decided_or_enacted,
                source_type=document.source_type.value,
                doc_type=document.doc_type.value,
                locator=hit.locator,
                extract=hit.text,
                source_url=document.source_url,
                is_binding=is_binding,
                authority_score=score_authority(factors, mode),
                fact_similarity=fact_sim_result.score if fact_sim_result else None,
                fact_similarity_explanation=fact_sim_result.explanation if fact_sim_result else None,
                legal_similarity=legal_sim_result.score if legal_sim_result else None,
                legal_similarity_explanation=legal_sim_result.explanation if legal_sim_result else None,
                treatment_summary=treatment_counts,
            )
        )

    results.sort(key=lambda r: r.authority_score, reverse=True)
    return results[:top_k]


@dataclass
class CitationEdge:
    citing_document_id: int
    citing_section_id: int | None
    citing_title: str
    citing_extract: str | None
    citing_source_url: str | None
    treatment_type: str
    confidence: float


def get_citation_treatment(document_id: int) -> list[CitationEdge]:
    """All documents that cite `document_id`, with how they treat it — the raw material
    for Precedent/Citation and Precedent-Attack agents (distinguish/limit/overrule signals).

    Carries citing_section_id/citing_extract (not just the document) so downstream
    agents can build a real SourceRef rather than a document-only, unverifiable claim.
    """
    with SessionLocal() as session:
        rows = session.scalars(select(Citation).where(Citation.cited_document_id == document_id))
        edges = []
        for row in rows:
            citing_doc = session.get(Document, row.citing_document_id)
            if citing_doc is None:
                continue
            citing_section = (
                session.get(DocumentSection, row.citing_section_id) if row.citing_section_id else None
            )
            edges.append(
                CitationEdge(
                    citing_document_id=citing_doc.id,
                    citing_section_id=citing_section.id if citing_section else None,
                    citing_title=citing_doc.title,
                    citing_extract=citing_section.text if citing_section else None,
                    citing_source_url=citing_doc.source_url,
                    treatment_type=row.treatment_type.value,
                    confidence=row.confidence,
                )
            )
        return edges
