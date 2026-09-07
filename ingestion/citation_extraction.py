"""Deterministic citation extraction — reuses Free Law Project's `eyecite` rather than
reimplementing citation parsing, per the architecture decision to not rebuild OSS
infrastructure that already exists for this exact problem."""

from dataclasses import dataclass

from eyecite import get_citations
from eyecite.models import FullCaseCitation, FullLawCitation


@dataclass
class ExtractedCitation:
    raw_text: str
    reporter: str | None
    volume: str | None
    page: str | None
    citation_type: str


def extract_citations(text: str) -> list[ExtractedCitation]:
    found = get_citations(text)
    extracted = []
    for citation in found:
        if isinstance(citation, FullCaseCitation):
            extracted.append(
                ExtractedCitation(
                    raw_text=citation.matched_text(),
                    reporter=citation.corrected_reporter(),
                    volume=citation.groups.get("volume"),
                    page=citation.groups.get("page"),
                    citation_type="case",
                )
            )
        elif isinstance(citation, FullLawCitation):
            # Law citations (e.g. "42 U.S.C. § 1985") carry title/reporter/section in
            # .groups, not a top-level .reporter attribute like case citations do.
            extracted.append(
                ExtractedCitation(
                    raw_text=citation.matched_text(),
                    reporter=citation.groups.get("reporter"),
                    volume=citation.groups.get("title"),
                    page=citation.groups.get("section"),
                    citation_type="statute",
                )
            )
    return extracted
