"""Query-driven federal statute ingestion: search GovInfo's USCODE collection, fetch
and parse each matching section, store it through the same pipeline as case law.

This only reaches federal statutes (GovInfo has no state codes) — a question that
turns on state law (e.g. a state's own election code) will not get a governing
statute from this pipeline no matter how well it runs; that gap is a source-coverage
limitation to disclose, not a bug to paper over (see docs/architecture.md §5/§19).
"""

from sqlalchemy import select

from ingestion.govinfo import BASE_URL, fetch_granule_text, search_uscode
from ingestion.pipeline import ingest_document
from ingestion.statute_parsing import parse_uscode_granule_html
from knowledge.db import SessionLocal
from knowledge.models import Document, DocType


def _already_ingested(citation_string: str) -> bool:
    with SessionLocal() as session:
        return session.scalar(select(Document).where(Document.citation_string == citation_string)) is not None


def _ingest_granule(txt_link: str, package_id: str, granule_id: str, jurisdiction_name: str) -> int | None:
    html = fetch_granule_text(txt_link)
    parsed = parse_uscode_granule_html(html)
    if parsed is None or not parsed.statutory_text:
        return None
    if _already_ingested(parsed.citation):
        return None

    return ingest_document(
        doc_type=DocType.STATUTE,
        title=parsed.heading,
        citation_string=parsed.citation,
        date_decided_or_enacted=None,
        full_text=parsed.statutory_text,
        source_provider="govinfo",
        source_url=f"https://www.govinfo.gov/app/details/{package_id}/{granule_id}",
        jurisdiction_name=jurisdiction_name,
    )


def ingest_statutes_matching_query(
    query: str,
    jurisdiction_name: str = "US-Federal",
    max_results: int = 5,
) -> list[int]:
    """Best for specific, distinctive phrases (e.g. an exact section heading) — a
    short/generic phrase (e.g. "voting rights") matches loosely against GovInfo's
    full-page index (including cross-reference notes, not just the operative text)
    and returns mostly-unrelated sections. For a known citation, use
    ingest_specific_statute instead of guessing a query that will hit it precisely.
    """
    results = search_uscode(query, max_results=max_results)
    ingested_ids: list[int] = []

    for result in results:
        txt_link = result.get("download", {}).get("txtLink")
        package_id = result.get("packageId")
        granule_id = result.get("granuleId")
        if not txt_link or not package_id or not granule_id:
            continue

        doc_id = _ingest_granule(txt_link, package_id, granule_id, jurisdiction_name)
        if doc_id is not None:
            ingested_ids.append(doc_id)

    return ingested_ids


def ingest_specific_statute(package_id: str, granule_id: str, jurisdiction_name: str = "US-Federal") -> int | None:
    """Ingests one known USCODE granule directly by id — e.g.
    ingest_specific_statute("USCODE-2024-title52", "USCODE-2024-title52-subtitleI-chap101-sec10101")
    for 52 U.S.C. § 10101. Use this when you already know which provision you want;
    it sidesteps search-relevance noise entirely.
    """
    txt_link = f"{BASE_URL}/packages/{package_id}/granules/{granule_id}/htm"
    return _ingest_granule(txt_link, package_id, granule_id, jurisdiction_name)
