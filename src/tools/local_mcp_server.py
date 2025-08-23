"""
Local MCP server (stdio) exposing simple, reliable tools for the agents.

Tools provided:
- http_fetch(url: str) -> {status, headers, text}
- extract_text(html: str) -> {text}
- keyword_extract(text: str, top_k: int=10) -> {keywords: [str]}

Implementation uses the MCP Python library's FastMCP helper for a minimal server
that communicates over stdio. The app will spawn this as a subprocess when
configured with connection.type=stdio in config/runconfig.yaml.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.fastmcp import FastMCP

# Reuse existing project utilities where possible
from src.tools.demo_tools import keyword_extract as demo_keyword_extract


app = FastMCP("local-mcp-tools")


@app.tool()
def http_fetch(url: str) -> Dict[str, object]:
    """Fetch a URL and return status, headers, and text content.

    Args:
        url: The URL to fetch via HTTP GET.
    Returns:
        Dict with keys: status (int), headers (dict[str,str]), text (str)
    """
    with httpx.Client(timeout=20) as client:
        resp = client.get(url)
        return {
            "status": resp.status_code,
            "headers": dict(resp.headers),
            "text": resp.text,
        }


@app.tool()
def extract_text(html: str) -> Dict[str, str]:
    """Extract naive plain text from HTML string.

    Note: This is intentionally simple to avoid new dependencies. Replace with a
    proper HTML parser if you need better fidelity.
    """
    # strip tags
    text = re.sub(r"<[^>]+>", " ", html or "")
    # collapse whitespace
    text = " ".join(text.split())
    return {"text": text}


@app.tool()
def keyword_extract(text: str, top_k: int = 10) -> Dict[str, List[str]]:
    """Extract top keywords from text using the project's demo utility."""
    top_k = int(top_k or 10)
    kws = demo_keyword_extract(text or "", top_k=top_k)
    return {"keywords": kws}


@app.tool()
def firecrawl_search(
    query: str,
    limit: int = 5,
    sources: Optional[List[str]] = None,
    scrape_formats: Optional[List[str]] = None,
    tbs: Optional[str] = None,
    location: Optional[str] = None,
    timeout_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """Search the web via Firecrawl and optionally scrape result content.

    Args:
        query: Search query string.
        limit: Max number of results to return.
        sources: Optional list of sources, e.g. ["web"], ["news"], ["images"].
        scrape_formats: Optional list of formats to scrape, e.g. ["markdown", "links"].
        tbs: Time-based search filter (e.g., "qdr:d" for past day).
        location: Geographic location (e.g., "Germany").
        timeout_ms: Timeout in milliseconds for the search.

    Returns:
        JSON-serializable dict including status, success, and data payload.
    """
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        return {"success": False, "error": "FIRECRAWL_API_KEY is not set in environment"}

    payload: Dict[str, Any] = {
        "query": query,
        "limit": int(limit or 5),
    }
    if sources:
        payload["sources"] = list(sources)
    if tbs:
        payload["tbs"] = tbs
    if location:
        payload["location"] = location
    if timeout_ms is not None:
        payload["timeout"] = int(timeout_ms)
    if scrape_formats:
        payload["scrapeOptions"] = {"formats": list(scrape_formats)}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            "https://api.firecrawl.dev/v2/search",
            headers=headers,
            json=payload,
        )
        try:
            body: Dict[str, Any] = resp.json()
        except Exception:
            body = {"raw": resp.text}

    return {
        "status": resp.status_code,
        "success": bool(body.get("success", resp.status_code == 200)),
        "data": body.get("data", body),
    }


if __name__ == "__main__":
    # Run as a stdio MCP server
    app.run_stdio()
