from unittest.mock import patch

import httpx

from retrieval.websearch import web_search


def _mock_response(payload, status_code=200):
    request = httpx.Request("POST", "https://api.tavily.com/search")
    return httpx.Response(status_code, json=payload, request=request)


def test_web_search_shapes_tavily_results():
    payload = {
        "results": [
            {"title": "Some Article", "url": "https://example.com/a", "content": "a snippet"},
            {"url": "https://example.com/b", "content": "no title here"},
        ]
    }
    with patch("retrieval.websearch.settings") as mock_settings, patch("httpx.post") as mock_post:
        mock_settings.tavily_api_key = "test-key"
        mock_post.return_value = _mock_response(payload)

        results = web_search("some query")

    assert len(results) == 2
    assert results[0].title == "Some Article"
    assert results[0].url == "https://example.com/a"
    assert results[0].snippet == "a snippet"
    assert results[1].title == "https://example.com/b"


def test_web_search_returns_empty_without_api_key():
    with patch("retrieval.websearch.settings") as mock_settings:
        mock_settings.tavily_api_key = ""
        assert web_search("some query") == []


def test_web_search_returns_empty_on_http_error():
    with patch("retrieval.websearch.settings") as mock_settings, patch("httpx.post") as mock_post:
        mock_settings.tavily_api_key = "test-key"
        mock_post.return_value = _mock_response({}, status_code=500)

        assert web_search("some query") == []
