"""The model's own general legal reasoning on the question, before any corpus
retrieval happens — the "an LLM can already answer simple questions" step. This is
what keeps the final answer from reading as an empty hedge when the local corpus is
thin: the answer is allowed to actually reason like a knowledgeable analyst, using
OPEN_REASONING grounding (general doctrine allowed by name; no invented specific
citations). Downstream retrieval and Source Verification still work exactly as
before for anything that claims to be a specific authority.
"""

from pydantic import BaseModel

from agents.llm import OPEN_REASONING, structured_complete
from agents.state import ResearchState
from retrieval.websearch import format_web_results_for_prompt

SYSTEM_PROMPT = (
    "Answer this legal question as a knowledgeable analyst would, using general "
    "legal knowledge and the web search results below. Be substantive and specific "
    "about how the relevant legal doctrines and tests apply to the facts given — do "
    "not hedge into a non-answer. This is a preliminary analysis that will later be "
    "checked against actual retrieved case law and statutes, so it's fine if it "
    "isn't perfectly precise; it should not be vague."
)


class PreliminaryAnswerOutput(BaseModel):
    analysis: str


def run(state: ResearchState) -> ResearchState:
    web_context = format_web_results_for_prompt(state.get("web_results", []))
    result = structured_complete(
        SYSTEM_PROMPT,
        f"QUESTION:\n{state['question']}\n\nWEB SEARCH RESULTS:\n{web_context}",
        PreliminaryAnswerOutput,
        model=state.get("model"),
        grounding=OPEN_REASONING,
    )
    return {**state, "preliminary_analysis": result.analysis}
