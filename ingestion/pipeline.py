"""SOURCE -> parse -> section/paragraph extraction -> citation extraction -> embed -> index.

Every document keeps its `source_provider`/`source_url`/`ingestion_status`/`last_verified_at`
(spec §18/§19) so coverage and currency limitations can be disclosed in an answer rather
than asserted by an LLM.
"""

from datetime import date, datetime

from sqlalchemy import select

from ingestion.citation_extraction import extract_citations
from ingestion.source_classification import classify_source_type
from knowledge.db import SessionLocal
from knowledge.models import (
    Citation,
    Court,
    Document,
    DocumentSection,
    DocType,
    ExtractedBy,
    IngestionStatus,
    Jurisdiction,
    SectionType,
    TreatmentType,
)
from retrieval.embeddings import embed_batch
from retrieval.opensearch_client import SECTIONS_INDEX, ensure_index, get_client


def _split_into_paragraphs(text: str) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n")]
    return [p for p in paragraphs if len(p) > 20]


def ingest_document(
    *,
    doc_type: DocType,
    title: str,
    citation_string: str | None,
    date_decided_or_enacted: date | None,
    full_text: str,
    source_provider: str,
    source_url: str | None,
    jurisdiction_name: str | None = None,
    court_name: str | None = None,
    license_note: str | None = None,
) -> int:
    """Ingests one document end to end. Returns the created `documents.id`.

    Citation edges are written with treatment_type=CITES and extracted_by=RULE — the
    finer treatment classification (distinguishes/overrules/etc.) is an agentic
    post-process (see agents/precedent_citation.py), not asserted at ingestion time.
    """
    source_type = classify_source_type(source_provider, doc_type.value)

    with SessionLocal() as session:
        jurisdiction = None
        if jurisdiction_name:
            jurisdiction = session.scalar(select(Jurisdiction).where(Jurisdiction.name == jurisdiction_name))
        court = None
        if court_name:
            court = session.scalar(select(Court).where(Court.name == court_name))

        document = Document(
            doc_type=doc_type,
            jurisdiction_id=jurisdiction.id if jurisdiction else None,
            court_id=court.id if court else None,
            title=title,
            citation_string=citation_string,
            date_decided_or_enacted=date_decided_or_enacted,
            source_type=source_type,
            source_url=source_url,
            source_provider=source_provider,
            license_note=license_note,
            ingestion_status=IngestionStatus.PROCESSING,
            last_verified_at=datetime.utcnow(),
        )
        session.add(document)
        session.flush()

        paragraphs = _split_into_paragraphs(full_text)
        sections = [
            DocumentSection(document_id=document.id, section_type=SectionType.PARAGRAPH, sequence=i, text=p)
            for i, p in enumerate(paragraphs)
        ]
        session.add_all(sections)
        session.flush()

        for section, paragraph in zip(sections, paragraphs):
            for citation in extract_citations(paragraph):
                cited_document = None
                if citation.citation_type == "case":
                    cited_document = session.scalar(
                        select(Document).where(Document.citation_string == citation.raw_text)
                    )
                session.add(
                    Citation(
                        citing_document_id=document.id,
                        citing_section_id=section.id,
                        cited_document_id=cited_document.id if cited_document else None,
                        citation_string_raw=citation.raw_text,
                        treatment_type=TreatmentType.CITES,
                        confidence=1.0 if cited_document else 0.5,
                        extracted_by=ExtractedBy.RULE,
                    )
                )

        session.flush()

        ensure_index()
        if paragraphs:
            vectors = embed_batch(paragraphs)
            client = get_client()
            for section, vector in zip(sections, vectors):
                embedding_ref = f"section-{section.id}"
                section.embedding_ref = embedding_ref
                client.index(
                    index=SECTIONS_INDEX,
                    id=embedding_ref,
                    body={
                        "document_id": document.id,
                        "section_id": section.id,
                        "text": section.text,
                        "locator": section.locator,
                        "jurisdiction": jurisdiction.name if jurisdiction else None,
                        "court_id": court.id if court else None,
                        "court_level": court.level if court else None,
                        "date": date_decided_or_enacted.isoformat() if date_decided_or_enacted else None,
                        "source_type": source_type.value,
                        "doc_type": doc_type.value,
                        "embedding": vector,
                    },
                )

        document.ingestion_status = IngestionStatus.COMPLETE
        session.commit()
        return document.id
