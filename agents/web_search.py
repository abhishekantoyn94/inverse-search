"""Deterministic node — a direct Tavily call, no LLM involved. Runs early (right after
issue decomposition) so its results are available as real context to every downstream
agent, especially synthesis — previously this ran last and only decorated the finished
answer with links the answer text never actually used."""

from agents.state import ResearchState
from retrieval.websearch import web_search


def run(state: ResearchState) -> ResearchState:
    results = web_search(state["question"])
    return {**state, "web_results": results}
