import os
from typing import Any, Dict

import pytest

from src.tools.local_mcp_server import notion_query_eligible, notion_update_status


class _MockResp:
    def __init__(self, status_code: int, body: Dict[str, Any]):
        self.status_code = status_code
        self._body = body
        self.text = "{\"mock\":true}"

    def json(self) -> Dict[str, Any]:
        return self._body


class _MockClientQuery:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url: str, headers: Dict[str, str], json: Dict[str, Any]):
        assert url.startswith("https://api.notion.com/v1/databases/") and url.endswith("/query")
        assert headers.get("Authorization", "").startswith("Bearer ")
        # Return one fake row shaped like Notion
        return _MockResp(
            200,
            {
                "results": [
                    {
                        "id": "page_123",
                        "properties": {
                            "Name": {
                                "id": "title",
                                "type": "title",
                                "title": [
                                    {"type": "text", "text": {"content": "Test Topic"}, "plain_text": "Test Topic"}
                                ],
                            },
                            "Status": {"id": "status", "type": "select", "select": {"name": "Not Started"}},
                        },
                    }
                ]
            },
        )


class _MockClientPatch:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def patch(self, url: str, headers: Dict[str, str], json: Dict[str, Any]):
        assert url.startswith("https://api.notion.com/v1/pages/")
        assert headers.get("Authorization", "").startswith("Bearer ")
        # Echo success
        return _MockResp(200, {"object": "page", "id": url.split("/")[-1]})


def test_notion_query_eligible_success(monkeypatch):
    # Ensure token set
    monkeypatch.setenv("NOTION_MCP_TOKEN", "notion-token")

    # Patch httpx.Client to our mock
    import httpx

    monkeypatch.setattr(httpx, "Client", _MockClientQuery)

    out = notion_query_eligible(database_id="db_abc", status_property="Status", status_value="Not Started", page_size=3)

    assert out["success"] is True
    assert out["status"] == 200
    assert out["count"] == 1
    assert out["results"][0]["title"] == "Test Topic"


def test_notion_update_status_success(monkeypatch):
    monkeypatch.setenv("NOTION_MCP_TOKEN", "notion-token")

    import httpx

    monkeypatch.setattr(httpx, "Client", _MockClientPatch)

    out = notion_update_status(page_id="page_123", status_property="Status", status_value="In Progress")
    assert out["success"] is True
    assert out["status"] == 200


def test_notion_tools_missing_token(monkeypatch):
    # Ensure token missing
    monkeypatch.delenv("NOTION_MCP_TOKEN", raising=False)

    out1 = notion_query_eligible(database_id="db_abc")
    out2 = notion_update_status(page_id="page_123")

    assert out1["success"] is False and "error" in out1
    assert out2["success"] is False and "error" in out2
