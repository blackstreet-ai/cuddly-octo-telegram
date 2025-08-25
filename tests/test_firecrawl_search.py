import os
from typing import Any, Dict

import pytest

# Import the tool function directly
from src.tools.local_mcp_server import tavily_search


class _MockResp:
    def __init__(self, status_code: int, body: Dict[str, Any]):
        self.status_code = status_code
        self._body = body
        self.text = "{\"mock\":true}"

    def json(self) -> Dict[str, Any]:
        return self._body


class _MockClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url: str, headers: Dict[str, str], json: Dict[str, Any]):
        # Basic assertion on request composition
        assert url == "https://api.tavily.com/search"
        assert headers.get("X-Tavily-API-Key", "").strip() != ""
        assert json.get("query") == "openai"
        # Return a minimal successful Tavily-like payload
        return _MockResp(
            200,
            {
                "query": "openai",
                "answer": "OpenAI is an AI research company.",
                "results": [
                    {
                        "url": "https://openai.com/",
                        "title": "OpenAI",
                        "content": "Creating safe AGI",
                    }
                ],
            },
        )


def test_tavily_search_success(monkeypatch):
    # Set API key
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-key")

    # Patch httpx.Client to our mock
    import httpx  # local import to allow monkeypatch

    monkeypatch.setattr(httpx, "Client", _MockClient)

    out = tavily_search(
        query="openai",
        max_results=1,
        search_depth="basic",
        include_answer=True,
        include_domains=["openai.com"],
        exclude_domains=["example.com"],
    )

    assert out["status"] == 200
    assert out["success"] is True
    assert isinstance(out.get("data"), dict)
    assert "results" in out["data"]
    assert out["data"]["results"][0]["url"].startswith("https://")


def test_tavily_search_missing_api_key(monkeypatch):
    # Ensure API key is absent
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    out = tavily_search(query="openai")

    assert out["success"] is False
    assert "error" in out
