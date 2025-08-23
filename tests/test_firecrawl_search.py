import os
from typing import Any, Dict

import pytest

# Import the tool function directly
from src.tools.local_mcp_server import firecrawl_search


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
        assert url == "https://api.firecrawl.dev/v2/search"
        assert headers.get("Authorization", "").startswith("Bearer ")
        assert json.get("query") == "openai"
        # Return a minimal successful Firecrawl-like payload
        return _MockResp(
            200,
            {
                "success": True,
                "data": {
                    "web": [
                        {
                            "url": "https://openai.com/",
                            "title": "OpenAI",
                            "description": "Creating safe AGI",
                            "position": 1,
                        }
                    ]
                },
            },
        )


def test_firecrawl_search_success(monkeypatch):
    # Set API key
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-key")

    # Patch httpx.Client to our mock
    import httpx  # local import to allow monkeypatch

    monkeypatch.setattr(httpx, "Client", _MockClient)

    out = firecrawl_search(
        query="openai",
        limit=1,
        sources=["web"],
        scrape_formats=["markdown"],
        tbs="qdr:d",
        location="US",
        timeout_ms=5000,
    )

    assert out["status"] == 200
    assert out["success"] is True
    assert isinstance(out.get("data"), dict)
    assert "web" in out["data"]
    assert out["data"]["web"][0]["url"].startswith("https://")


def test_firecrawl_search_missing_api_key(monkeypatch):
    # Ensure API key is absent
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    out = firecrawl_search(query="openai")

    assert out["success"] is False
    assert "error" in out
