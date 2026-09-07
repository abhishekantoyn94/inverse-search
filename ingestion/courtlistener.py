"""Client for the CourtListener / Free Law Project REST API (free, registration required).

Used for case law fetch. Court hierarchy/jurisdiction metadata is resolved separately
via the `courts-db` library (see ingestion/source_classification.py), not by
re-deriving it from CourtListener responses.
"""

from collections.abc import Iterator
from typing import Any

import httpx

from settings import settings

BASE_URL = "https://www.courtlistener.com/api/rest/v4"
SITE_URL = "https://www.courtlistener.com"


def absolute_url(path: str) -> str:
    """CourtListener's `absolute_url` field is a site-relative path (e.g.
    '/opinion/123/case-name/'), not a full URL despite the name — every caller that
    stores it as a hyperlink (ingestion/pipeline.py) must go through this."""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{SITE_URL}{path}"


def _client() -> httpx.Client:
    headers = {"Authorization": f"Token {settings.courtlistener_api_token}"} if settings.courtlistener_api_token else {}
    return httpx.Client(base_url=BASE_URL, headers=headers, timeout=30.0)


def fetch_opinions(
    court_id: str | None = None,
    date_filed_after: str | None = None,
    page_size: int = 20,
) -> Iterator[dict[str, Any]]:
    """Yields raw opinion records (id, plain_text/html, cluster, absolute_url, ...).

    Paginates through CourtListener's cursor-based pagination until exhausted.
    """
    params: dict[str, Any] = {"page_size": page_size}
    if court_id:
        params["cluster__docket__court"] = court_id
    if date_filed_after:
        params["cluster__date_filed__gte"] = date_filed_after

    with _client() as client:
        url = "/opinions/"
        while url:
            response = client.get(url, params=params if url == "/opinions/" else None)
            response.raise_for_status()
            payload = response.json()
            yield from payload["results"]
            url = payload.get("next")
            params = {}


def fetch_cluster(cluster_id: int) -> dict[str, Any]:
    """A cluster groups an opinion with its citations, court, and date_filed — the
    metadata needed to populate `documents.citation_string` / `date_decided_or_enacted`."""
    with _client() as client:
        response = client.get(f"/clusters/{cluster_id}/")
        response.raise_for_status()
        return response.json()
