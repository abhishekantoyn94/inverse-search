from pydantic import BaseModel

from agents.context_format import format_authorities
from agents.llm import structured_complete
from agents.schemas import InversePropositionOutput
from agents.state import ResearchState
from ranking.legal_reranker import ResearchMode as RankingMode
from research.schemas import Claim, InverseResearch, ResearchMode
from retrieval.hybrid_search import MetadataFilter
from retrieval.toolkit import search_authorities

INVERT_SYSTEM_PROMPT = (
    "State the logical inverse of the user's proposition — i.e. the strongest version "
    "of the opposite legal conclusion on the same facts. Be precise: invert the legal "
    "conclusion, not the facts."
)

RESEARCH_INVERSE_PROMPT = (
    "Using only the RETRIEVED AUTHORITIES, identify which of them actually support the "
    "INVERSE PROPOSITION below, and note any alternative interpretation of the governing "
    "law that would favor it. Every 'authority' claim must cite document_id/section_id; "
    "if the authorities only weakly support the inverse, use claim_type 'inference' or "
    "'speculation' and say so. If a retrieved authority is topically unrelated to the "
    "inverse proposition (a small corpus can retrieve something merely closest-of-a-bad-"
    "lot), leave it out entirely rather than stretching it into apparent relevance."
)


class InverseSupportOutput(BaseModel):
    authorities_supporting_inverse: list[Claim]
    alternative_interpretation: Claim | None = None


def run(state: ResearchState) -> ResearchState:
    if ResearchMode.INVERSE not in state.get("requested_modes", []):
        return state

    inverted: InversePropositionOutput = structured_complete(
        INVERT_SYSTEM_PROMPT, state["question"], InversePropositionOutput, model=state.get("model")
    )

    authorities = search_authorities(
        inverted.inverse_proposition,
        mode=RankingMode.INVERSE,
        filters=MetadataFilter(
            jurisdictions=[state["target_jurisdiction"]] if state.get("target_jurisdiction") else [],
            doc_types=["case"],
        ),
        target_jurisdiction=state.get("target_jurisdiction"),
    )
    if not authorities:
        # Nothing cleared the relevance floor — deterministically empty, no LLM call.
        return {
            **state,
            "inverse_research": InverseResearch(inverse_proposition=inverted.inverse_proposition),
        }

    support: InverseSupportOutput = structured_complete(
        RESEARCH_INVERSE_PROMPT,
        f"INVERSE PROPOSITION:\n{inverted.inverse_proposition}\n\n"
        f"RETRIEVED AUTHORITIES:\n{format_authorities(authorities)}",
        InverseSupportOutput,
        model=state.get("model"),
    )
    return {
        **state,
        "inverse_research": InverseResearch(
            inverse_proposition=inverted.inverse_proposition,
            authorities_supporting_inverse=support.authorities_supporting_inverse,
            alternative_interpretation=support.alternative_interpretation,
        ),
    }
