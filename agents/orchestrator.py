"""The Orchestrator: a LangGraph state machine, not a chat loop, so which agents run
for a given question is inspectable and testable rather than emergent. Each node
checks `requested_modes` itself and no-ops if its mode wasn't asked for (spec §4: "the
Orchestrator should determine which agents are required for a given question") — for
MVP scale this per-node gate is simpler and just as correct as skipping graph edges.
"""

from langgraph.graph import END, START, StateGraph

from agents import (
    adversarial,
    case_research,
    inverse_research,
    issue_decomposition,
    precedent_citation,
    preliminary_answer,
    source_verification,
    statute_research,
    synthesis,
    web_search,
)
from agents.state import ResearchState
from research.schemas import ResearchMode
from settings import settings


def build_graph():
    graph = StateGraph(ResearchState)

    graph.add_node("issue_decomposition", issue_decomposition.run)
    graph.add_node("web_search", web_search.run)
    graph.add_node("preliminary_answer", preliminary_answer.run)
    graph.add_node("statute_research", statute_research.run)
    graph.add_node("case_research_direct", case_research.run_direct)
    graph.add_node("case_research_fact", case_research.run_fact_similarity)
    graph.add_node("case_research_legal", case_research.run_legal_similarity)
    graph.add_node("precedent_citation", precedent_citation.run)
    graph.add_node("inverse_research", inverse_research.run)
    graph.add_node("adversarial", adversarial.run)
    graph.add_node("synthesis", synthesis.run)
    graph.add_node("source_verification", source_verification.run)

    graph.add_edge(START, "issue_decomposition")
    graph.add_edge("issue_decomposition", "web_search")
    graph.add_edge("web_search", "preliminary_answer")
    graph.add_edge("preliminary_answer", "statute_research")
    graph.add_edge("statute_research", "case_research_direct")
    graph.add_edge("case_research_direct", "case_research_fact")
    graph.add_edge("case_research_fact", "case_research_legal")
    graph.add_edge("case_research_legal", "precedent_citation")
    graph.add_edge("precedent_citation", "inverse_research")
    graph.add_edge("inverse_research", "adversarial")
    graph.add_edge("adversarial", "synthesis")
    graph.add_edge("synthesis", "source_verification")
    graph.add_edge("source_verification", END)

    return graph.compile()


def run_research(
    question: str,
    target_jurisdiction: str,
    modes: list[ResearchMode],
    model: str | None = None,
) -> ResearchState:
    app = build_graph()
    initial_state: ResearchState = {
        "question": question,
        "target_jurisdiction": target_jurisdiction,
        "requested_modes": modes,
        "model": model or settings.openai_chat_model,
    }
    return app.invoke(initial_state)
