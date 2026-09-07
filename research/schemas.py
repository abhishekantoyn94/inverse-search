"""The structured research answer (spec §15) and its building blocks.

Every substantive proposition is a Claim carrying a claim_type (spec §5: authority /
inference / analogy / speculation / unresolved) and, where it is or relies on an
authority, a SourceRef with an exact document/section/locator/extract pointer. The
Source Verification agent walks every Claim.source in a StructuredAnswer and confirms
it resolves to a real, retrieved document_sections row before the answer ships.
"""

from datetime import date
from enum import Enum

from pydantic import BaseModel


class ResearchMode(str, Enum):
    DIRECT = "direct"
    FACT_SIMILARITY = "fact_similarity"
    LEGAL_SIMILARITY = "legal_similarity"
    CITATION = "citation"
    STATUTORY = "statutory"
    INVERSE = "inverse"
    ADVERSARIAL = "adversarial"
    PRECEDENT_ATTACK = "precedent_attack"
    # Phase 2 — present in the contract now so the UI/API don't need breaking changes,
    # but agents for these are not implemented in the MVP (see docs/architecture.md §7).
    COMPARATIVE = "comparative"
    ANALOGY = "analogy"
    NOVEL_AREA = "novel_area"
    HISTORICAL = "historical"


class ClaimType(str, Enum):
    AUTHORITY = "authority"
    INFERENCE = "inference"
    ANALOGY = "analogy"
    SPECULATION = "speculation"
    UNRESOLVED = "unresolved"


class SourceRef(BaseModel):
    document_id: int
    section_id: int
    title: str
    citation_string: str | None = None
    locator: str | None = None
    extract: str
    source_url: str | None = None


class WebResult(BaseModel):
    """A live web-search hit (Tavily) — always discovery-tier (docs/architecture.md §7),
    never merged with or presented as legal authority."""

    title: str
    url: str
    snippet: str


class Claim(BaseModel):
    text: str
    claim_type: ClaimType
    source: SourceRef | None = None
    confidence: float = 1.0
    verified: bool = False


class AdversarialAnalysis(BaseModel):
    strongest_argument_for: Claim
    strongest_argument_against: Claim
    weaknesses: list[Claim] = []
    likely_opposing_authorities: list[Claim] = []
    possible_responses: list[Claim] = []


class InverseResearch(BaseModel):
    inverse_proposition: str
    authorities_supporting_inverse: list[Claim] = []
    alternative_interpretation: Claim | None = None


class StructuredAnswer(BaseModel):
    question: str
    short_answer: str
    jurisdiction: str
    material_facts: list[str] = []
    issues: list[str] = []
    governing_statutes: list[Claim] = []
    binding_authorities: list[Claim] = []
    persuasive_authorities: list[Claim] = []
    factually_similar_authorities: list[Claim] = []
    legally_similar_authorities: list[Claim] = []
    authorities_supporting: list[Claim] = []
    authorities_against: list[Claim] = []
    distinguishing_authorities: list[Claim] = []
    adversarial_analysis: AdversarialAnalysis
    inverse_research: InverseResearch
    comparative_authorities: list[Claim] = []
    novel_or_analogous_authorities: list[Claim] = []
    unresolved_questions: list[str] = []
    research_gaps: list[str] = []
    conclusion: str

    # Coverage disclosure (spec §19) — populated deterministically from what was
    # actually queried, never asserted by an agent.
    jurisdiction_coverage_note: str
    date_coverage_note: str
    modes_not_yet_researched: list[ResearchMode] = []

    # Live web cross-check (discovery-tier only, spec §7) — populated deterministically
    # by a direct Tavily call, not agentic.
    web_verification: list[WebResult] = []
