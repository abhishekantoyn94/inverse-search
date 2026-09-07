"""Client for the GovInfo API (free, official) — US Code, CFR, Federal Register, Statutes
at Large. Every endpoint here has been verified live against the real API (its shapes
are not what GovInfo's own docs examples suggest in a few places, e.g. `/search` needs
`offsetMark`, and a granule's `download.txtLink` is a ready-to-fetch absolute URL)."""

from typing import Any

import httpx

from settings import settings

BASE_URL = "https://api.govinfo.gov"


def _api_key() -> str:
    # An explicitly-set-but-empty GOVINFO_API_KEY in .env overrides the Settings
    # class default, so fall back to the public demo key here too, not just there.
    return settings.govinfo_api_key or "DEMO_KEY"


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, params={"api_key": _api_key()}, timeout=30.0)


def search_uscode(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """Full-text search scoped to the USCODE collection. Each result carries
    `download.txtLink` (ready to fetch via fetch_granule_text) and a `resultLink`
    granule-summary URL — no need to guess a granule's chapter/subchapter path.

    The query is phrase-quoted: an unquoted multi-word query is scored as a loose
    OR-of-terms match and returns mostly-unrelated sections (verified live — e.g.
    unquoted "civil action for deprivation of rights" surfaced immigration and
    aircraft-training provisions ahead of the actual 42 U.S.C. § 1983 section).
    Quoting scopes it to an actual phrase match.
    """
    with _client() as client:
        response = client.post(
            "/search",
            json={"query": f'collection:USCODE AND "{query}"', "pageSize": max_results, "offsetMark": "*"},
        )
        response.raise_for_status()
        return response.json().get("results", [])


def fetch_granule_text(txt_link: str) -> str:
    """Fetches the rendered HTML for one USCODE granule (a single section) — this is
    the `download.txtLink` from a search result or granule summary, already absolute."""
    response = httpx.get(txt_link, params={"api_key": _api_key()}, timeout=30.0)
    response.raise_for_status()
    return response.text
