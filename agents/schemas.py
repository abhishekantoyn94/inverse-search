"""LLM-facing output schemas — thin wrappers so agents/llm.py's structured_complete has
something to parse into. Kept separate from research/schemas.py (the persisted/API
contract) because these are call-scoped, not part of the final StructuredAnswer shape."""

from pydantic import BaseModel

from research.schemas import Claim


class IssueDecompositionOutput(BaseModel):
    jurisdiction: str
    court_hierarchy_note: str
    issues: list[str]
    material_facts: list[str]


class ClaimsOutput(BaseModel):
    claims: list[Claim]


class InversePropositionOutput(BaseModel):
    inverse_proposition: str


class AdversarialOutput(BaseModel):
    strongest_argument_for: Claim
    strongest_argument_against: Claim
    weaknesses: list[Claim]
    possible_responses: list[Claim]


class SynthesisTextOutput(BaseModel):
    short_answer: str
    conclusion: str
    unresolved_questions: list[str]
    research_gaps: list[str]
