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

import re
from typing import Dict, List

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


if __name__ == "__main__":
    # Run as a stdio MCP server
    app.run_stdio()
