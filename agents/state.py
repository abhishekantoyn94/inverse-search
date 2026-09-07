from typing import TypedDict

from research.schemas import AdversarialAnalysis, Claim, InverseResearch, ResearchMode, WebResult


class ResearchState(TypedDict, total=False):
    question: str
    target_jurisdiction: str
    requested_modes: list[ResearchMode]
    model: str

    web_results: list[WebResult]  # fetched early so synthesis can actually use them
    preliminary_analysis: str  # the model's own general legal reasoning, pre-retrieval

    issues: list[str]
    material_facts: list[str]

    governing_statutes: list[Claim]
    binding_authorities: list[Claim]
    persuasive_authorities: list[Claim]
    factually_similar_authorities: list[Claim]
    legally_similar_authorities: list[Claim]
    authorities_supporting: list[Claim]
    authorities_against: list[Claim]
    distinguishing_authorities: list[Claim]

    inverse_research: InverseResearch
    adversarial_analysis: AdversarialAnalysis

    unresolved_questions: list[str]
    research_gaps: list[str]

    final_answer: dict  # StructuredAnswer.model_dump(), set by the synthesis node
    verification_report: dict  # set by the source-verification node
