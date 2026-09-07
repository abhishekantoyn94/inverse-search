"""Live web cross-check via Tavily — deterministic, not agentic (a direct API call,
no LLM judgment involved). Results are always discovery-tier (docs/architecture.md §7):
useful as an external sanity check, never presented as or merged with legal authority.
"""

import httpx

from research.schemas import WebResult
from settings import settings

TAVILY_URL = "https://api.tavily.com/search"


def web_search(query: str, max_results: int = 4) -> list[WebResult]:
    if not settings.tavily_api_key:
        return []

    try:
        response = httpx.post(
            TAVILY_URL,
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            },
            timeout=15.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return []

    results = response.json().get("results", [])
    return [
        WebResult(title=r.get("title", r["url"]), url=r["url"], snippet=r.get("content", ""))
        for r in results
    ]


def format_web_results_for_prompt(results: list[WebResult]) -> str:
    """Renders web results for inclusion in an agent prompt — used by
    preliminary_answer, synthesis, and chat_reply so search results actually inform
    the generated text, not just get appended as decorative links afterward."""
    if not results:
        return "(no web results)"
    return "\n---\n".join(f"{r.title}\n{r.url}\n{r.snippet}" for r in results)
