from agents.context_format import format_authorities
from agents.llm import structured_complete
from agents.schemas import ClaimsOutput
from agents.state import ResearchState
from ranking.legal_reranker import ResearchMode as RankingMode
from research.schemas import ResearchMode
from retrieval.hybrid_search import MetadataFilter
from retrieval.toolkit import search_authorities

SYSTEM_PROMPT = (
    "Using only the RETRIEVED AUTHORITIES, identify the statutes/sections that "
    "actually govern the issues below, including relevant definitions, amendments, "
    "and any judicial interpretation shown in the extracts. Every claim must be type "
    "'authority' and cite its document_id/section_id, unless no retrieved authority "
    "actually supports it — in that case, omit the claim rather than guessing. A "
    "small corpus will sometimes retrieve a statute with nothing genuinely to do "
    "with the question (e.g. an immigration provision retrieved for a contract "
    "dispute) — do not stretch such a statute into relevance; leave it out."
)


def run(state: ResearchState) -> ResearchState:
    if ResearchMode.STATUTORY not in state.get("requested_modes", []):
        return {**state, "governing_statutes": []}

    query = " ".join(state.get("issues", [])) or state["question"]
    authorities = search_authorities(
        query,
        mode=RankingMode.STATUTORY,
        filters=MetadataFilter(
            jurisdictions=[state["target_jurisdiction"]] if state.get("target_jurisdiction") else [],
            doc_types=["statute", "regulation"],
        ),
        target_jurisdiction=state.get("target_jurisdiction"),
    )
    if not authorities:
        # Nothing cleared the relevance floor — deterministically empty, no LLM call.
        return {**state, "governing_statutes": []}

    result: ClaimsOutput = structured_complete(
        SYSTEM_PROMPT,
        f"ISSUES:\n{query}\n\nRETRIEVED AUTHORITIES:\n{format_authorities(authorities)}",
        ClaimsOutput,
        model=state.get("model"),
    )
    return {**state, "governing_statutes": result.claims}
