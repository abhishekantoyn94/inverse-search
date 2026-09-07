from pydantic import BaseModel

from agents.context_format import format_authorities
from agents.llm import structured_complete
from agents.state import ResearchState
from ranking.legal_reranker import ResearchMode as RankingMode
from ranking.similarity import FactProfile, LegalProfile
from research.schemas import Claim, ResearchMode
from retrieval.hybrid_search import MetadataFilter
from retrieval.toolkit import search_authorities


class DirectResearchOutput(BaseModel):
    binding_authorities: list[Claim]
    persuasive_authorities: list[Claim]
    authorities_supporting: list[Claim]
    authorities_against: list[Claim]


class SimilarityClaimsOutput(BaseModel):
    claims: list[Claim]


DIRECT_SYSTEM_PROMPT = (
    "Using only the RETRIEVED AUTHORITIES, split them into binding vs persuasive "
    "(use the 'Binding' field on each authority), and separately classify each as "
    "supporting or opposing the user's proposition based on its actual holding/extract. "
    "An authority can appear in both a binding/persuasive list and a supporting/opposing "
    "list. Every claim must cite its document_id/section_id and be type 'authority'; if "
    "an authority is ambiguous, mark that claim type 'inference' instead and say why. "
    "CRITICAL: first judge whether each retrieved authority is actually topically "
    "relevant to the proposition — retrieval returns whatever is closest in a small "
    "corpus even when nothing is truly on point. If a retrieved authority's actual "
    "subject matter has nothing to do with the proposition (e.g. an election-law "
    "case retrieved for a software-liability question), DO NOT cite it or describe "
    "it as supporting/opposing anything — leave it out entirely rather than "
    "mischaracterizing what it actually holds. Empty lists are the correct, honest "
    "output when nothing retrieved is genuinely on point."
)

FACT_SIM_SYSTEM_PROMPT = (
    "Using only the RETRIEVED AUTHORITIES (already scored for factual similarity), "
    "write one claim per authority that is genuinely factually similar, explaining WHY, "
    "quoting the similarity score and explanation given. Do not comment on legal "
    "similarity here. Skip any authority whose facts have nothing meaningfully in "
    "common with the query facts — a low similarity score plus an actually unrelated "
    "fact pattern means omit it, not force an explanation."
)

LEGAL_SIM_SYSTEM_PROMPT = (
    "Using only the RETRIEVED AUTHORITIES (already scored for legal similarity), write "
    "one claim per authority that is genuinely legally similar, explaining WHY it "
    "applies a similar legal principle/test, quoting the similarity score and "
    "explanation given, even where facts differ. Skip any authority that doesn't "
    "actually share a legal issue or doctrine with the query — omit it rather than "
    "force an explanation for an unrelated authority."
)


def _filters(state: ResearchState) -> MetadataFilter:
    jurisdiction = state.get("target_jurisdiction")
    return MetadataFilter(jurisdictions=[jurisdiction] if jurisdiction else [], doc_types=["case"])


def run_direct(state: ResearchState) -> ResearchState:
    if ResearchMode.DIRECT not in state.get("requested_modes", []):
        return state

    query = " ".join(state.get("issues", [])) or state["question"]
    authorities = search_authorities(
        query, mode=RankingMode.DIRECT, filters=_filters(state), target_jurisdiction=state.get("target_jurisdiction")
    )
    if not authorities:
        # Nothing cleared the relevance floor — deterministically empty, no LLM call.
        # An LLM shown zero authorities can still be tempted to reason about what
        # "might" apply; not calling it at all removes that failure mode entirely.
        return {
            **state,
            "binding_authorities": [],
            "persuasive_authorities": [],
            "authorities_supporting": [],
            "authorities_against": [],
        }

    result: DirectResearchOutput = structured_complete(
        DIRECT_SYSTEM_PROMPT,
        f"PROPOSITION:\n{state['question']}\n\nRETRIEVED AUTHORITIES:\n{format_authorities(authorities)}",
        DirectResearchOutput,
        model=state.get("model"),
    )
    return {
        **state,
        "binding_authorities": result.binding_authorities,
        "persuasive_authorities": result.persuasive_authorities,
        "authorities_supporting": result.authorities_supporting,
        "authorities_against": result.authorities_against,
    }


def run_fact_similarity(state: ResearchState) -> ResearchState:
    if ResearchMode.FACT_SIMILARITY not in state.get("requested_modes", []):
        return {**state, "factually_similar_authorities": []}

    fact_profile = FactProfile(narrative=" ".join(state.get("material_facts", [])) or state["question"])
    authorities = search_authorities(
        fact_profile.narrative,
        mode=RankingMode.FACT_SIMILARITY,
        filters=_filters(state),
        target_jurisdiction=state.get("target_jurisdiction"),
        fact_profile=fact_profile,
    )
    result: SimilarityClaimsOutput = structured_complete(
        FACT_SIM_SYSTEM_PROMPT,
        f"QUERY FACTS:\n{fact_profile.narrative}\n\nRETRIEVED AUTHORITIES:\n{format_authorities(authorities)}",
        SimilarityClaimsOutput,
        model=state.get("model"),
    )
    return {**state, "factually_similar_authorities": result.claims}


def run_legal_similarity(state: ResearchState) -> ResearchState:
    if ResearchMode.LEGAL_SIMILARITY not in state.get("requested_modes", []):
        return {**state, "legally_similar_authorities": []}

    legal_profile = LegalProfile(narrative=" ".join(state.get("issues", [])) or state["question"])
    authorities = search_authorities(
        legal_profile.narrative,
        mode=RankingMode.LEGAL_SIMILARITY,
        filters=_filters(state),
        target_jurisdiction=state.get("target_jurisdiction"),
        legal_profile=legal_profile,
    )
    result: SimilarityClaimsOutput = structured_complete(
        LEGAL_SIM_SYSTEM_PROMPT,
        f"QUERY ISSUES:\n{legal_profile.narrative}\n\nRETRIEVED AUTHORITIES:\n{format_authorities(authorities)}",
        SimilarityClaimsOutput,
        model=state.get("model"),
    )
    return {**state, "legally_similar_authorities": result.claims}
