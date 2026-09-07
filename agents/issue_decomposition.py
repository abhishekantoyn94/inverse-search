from agents.llm import structured_complete
from agents.schemas import IssueDecompositionOutput
from agents.state import ResearchState

SYSTEM_PROMPT = (
    "Decompose the user's legal question into discrete legal issues. Identify the "
    "governing jurisdiction (state it explicitly even if the user didn't) and note the "
    "relevant court hierarchy in one sentence. Extract only the facts the user actually "
    "gave — do not invent facts."
)


def run(state: ResearchState) -> ResearchState:
    result: IssueDecompositionOutput = structured_complete(
        SYSTEM_PROMPT,
        state["question"],
        IssueDecompositionOutput,
        model=state.get("model"),
    )
    return {
        **state,
        "target_jurisdiction": state.get("target_jurisdiction") or result.jurisdiction,
        "issues": result.issues,
        "material_facts": result.material_facts,
    }
