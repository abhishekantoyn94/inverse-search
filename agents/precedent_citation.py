from pydantic import BaseModel

from agents.llm import structured_complete
from agents.state import ResearchState
from research.schemas import Claim, ResearchMode, SourceRef
from retrieval.toolkit import CitationEdge, get_citation_treatment

_NEGATIVE_TREATMENTS = {"overrules", "criticises", "departs_from", "distinguishes", "narrows"}


class DistinctionOutput(BaseModel):
    claims: list[Claim]


SYSTEM_PROMPT = (
    "For each citing case below, the treatment_type describes how it treated the "
    "target authority. Write one claim per negative-treatment entry (distinguishes / "
    "narrows / criticises / overrules / departs_from) explaining what it means for the "
    "target authority's reliability. Type these claims 'authority' since the treatment "
    "relationship itself is not in dispute — but if you must infer WHY beyond the raw "
    "treatment_type label, mark that inference explicitly."
)


def run(state: ResearchState) -> ResearchState:
    modes = state.get("requested_modes", [])
    if ResearchMode.CITATION not in modes and ResearchMode.PRECEDENT_ATTACK not in modes:
        return {**state, "distinguishing_authorities": []}

    target_authorities = [
        claim for claim in state.get("binding_authorities", []) + state.get("persuasive_authorities", [])
        if claim.source is not None
    ]
    if not target_authorities:
        return {**state, "distinguishing_authorities": []}

    edges: list[CitationEdge] = []
    for claim in target_authorities:
        edges.extend(get_citation_treatment(claim.source.document_id))

    negative_edges = [
        e for e in edges if e.treatment_type in _NEGATIVE_TREATMENTS and e.citing_section_id is not None
    ]
    if not negative_edges:
        return {**state, "distinguishing_authorities": []}

    context = "\n---\n".join(
        f"[document_id={e.citing_document_id} section_id={e.citing_section_id}]\n"
        f"Title: {e.citing_title!r}\nTreatment: {e.treatment_type} (confidence {e.confidence})\n"
        f"Extract: {e.citing_extract}"
        for e in negative_edges
    )
    result: DistinctionOutput = structured_complete(SYSTEM_PROMPT, context, DistinctionOutput, model=state.get("model"))
    return {**state, "distinguishing_authorities": result.claims}
