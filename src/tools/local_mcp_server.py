"""
Local MCP server (stdio) exposing simple, reliable tools for the agents.

Tools provided:
- http_fetch(url: str) -> {status, headers, text}
- extract_text(html: str) -> {text}
- tavily_search(...) -> Tavily web search response summary
- firecrawl_search(...) -> Firecrawl search response summary (kept for backward-compat)

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
from dotenv import load_dotenv


# Load variables from .env so subprocess has access to keys like FIRECRAWL_API_KEY
load_dotenv()

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


# Note: Keyword extraction demo tool removed to decouple from local demo utilities.


# ------------------------------
# Tavily Search MCP tool
# ------------------------------

@app.tool()
def tavily_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_answer: bool = False,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Search the web via Tavily.

    Args:
        query: Search query string.
        max_results: Max number of results to return (1-10 typical).
        search_depth: "basic" (faster) or "advanced" (deeper crawling) per Tavily API.
        include_answer: If true, request Tavily's synthesized answer when available.
        include_domains: Optional list of domains to prioritize/include.
        exclude_domains: Optional list of domains to exclude.

    Returns:
        JSON-serializable dict including status, success, and data payload.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"success": False, "error": "TAVILY_API_KEY is not set in environment"}

    payload: Dict[str, Any] = {
        "query": query,
        "max_results": int(max_results or 5),
        "search_depth": search_depth or "basic",
    }
    # Common Tavily flags
    if include_answer:
        payload["include_answer"] = True
    if include_domains:
        payload["include_domains"] = list(include_domains)
    if exclude_domains:
        payload["exclude_domains"] = list(exclude_domains)

    # Prefer header auth; some clients also support api_key in body. We set both for robustness.
    headers = {
        "Content-Type": "application/json",
        "X-Tavily-API-Key": api_key,
    }
    payload.setdefault("api_key", api_key)

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            "https://api.tavily.com/search",
            headers=headers,
            json=payload,
        )
        try:
            body: Dict[str, Any] = resp.json()
        except Exception:
            body = {"raw": resp.text}

    # Tavily typically returns 200 with fields like results, answer, query, etc.
    return {
        "status": resp.status_code,
        "success": resp.status_code == 200,
        "data": body,
    }


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


# ------------------------------
# Notion MCP tools
# ------------------------------

def _notion_headers() -> Dict[str, str]:
    """Build headers for Notion API from env.

    Requires NOTION_MCP_TOKEN to be set in env (e.g., via .env and load_dotenv()).
    """
    token = os.getenv("NOTION_MCP_TOKEN")
    if not token:
        # Return headers that will certainly fail so the tool can report a clear error
        return {}
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


@app.tool()
def notion_query_eligible(
    database_id: Optional[str] = None,
    status_property: str = "Status",
    status_value: str = "Not Started",
    property_type: str = "select",
    page_size: int = 5,
) -> Dict[str, Any]:
    """Query a Notion database for rows eligible to process.

    Args:
        database_id: The Notion database ID.
        status_property: Name of the select property used to track status (default: "Status").
        status_value: Select option value indicating eligibility (default: "Not Started").
        property_type: Property schema to use for filtering: "select" (default) or "status" for newer Notion databases.
        page_size: Max number of rows to return.
    Returns:
        Dict containing success flag and minimal page info list [{page_id, title, properties}].
    """
    headers = _notion_headers()
    if not headers:
        return {"success": False, "error": "NOTION_MCP_TOKEN not set in environment"}

    # Resolve database_id from env if not provided
    if not database_id:
        database_id = os.getenv("NOTION_DATABASE_ID")
        if not database_id:
            return {
                "success": False,
                "error": "database_id not provided and NOTION_DATABASE_ID not set in environment",
            }

    def _alt_values(val: str) -> List[str]:
        # Try common capitalization variants
        alts = set()
        alts.add(val)
        if val.lower() == "not started":
            alts.update(["Not started", "Not Started"])
        elif val.lower() == "in progress":
            alts.update(["In progress", "In Progress"])
        elif val.lower() == "done":
            alts.update(["Done"])
        else:
            # generic title-case fallback
            alts.add(val.title())
        return list(alts)

    def _build_payload(filter_key: str, value: str) -> Dict[str, Any]:
        # Use timestamp-based sort; Notion rejects `property: last_edited_time`
        return {
            "filter": {
                "property": status_property,
                filter_key: {"equals": value},
            },
            "page_size": int(page_size or 5),
            "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}],
        }

    def _try_query(client: httpx.Client, filter_key: str, value: str) -> tuple[int, Dict[str, Any]]:
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        resp = client.post(url, headers=headers, json=_build_payload(filter_key, value))
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
        return resp.status_code, data

    with httpx.Client(timeout=30) as client:
        preferred_key = "select" if (property_type or "select").lower() == "select" else "status"
        fallback_key = "status" if preferred_key == "select" else "select"

        # Try preferred key with value and alternates
        status_code, data = _try_query(client, preferred_key, status_value)
        if status_code != 200:
            # Try fallback key with original value
            status_code, data = _try_query(client, fallback_key, status_value)
        if status_code == 200 and not data.get("results"):
            # Try alternate capitalization on preferred key first, then fallback key
            for v in _alt_values(status_value):
                status_code, data = _try_query(client, preferred_key, v)
                if status_code == 200 and data.get("results"):
                    break
            if status_code == 200 and not data.get("results"):
                for v in _alt_values(status_value):
                    status_code, data = _try_query(client, fallback_key, v)
                    if status_code == 200 and data.get("results"):
                        break

    results = []
    for row in data.get("results", []):
        page_id = row.get("id")
        props = row.get("properties", {})
        # Try to derive a title from a common title prop if present
        title = None
        for prop in props.values():
            if isinstance(prop, dict) and prop.get("type") == "title":
                items = prop.get("title") or []
                if items:
                    title = items[0].get("plain_text") or items[0].get("text", {}).get("content")
                    break
        results.append({"page_id": page_id, "title": title, "properties": props})

    result_obj = {
        "success": status_code == 200,
        "status": status_code,
        "count": len(results),
        "results": results,
    }
    # Attach minimal debug info when unsuccessful or empty
    if status_code != 200:
        result_obj["notion_error"] = data
    elif not results:
        result_obj["debug"] = {
            "tried_property_type_preference": (property_type or "select").lower(),
            "status_value": status_value,
        }
    return result_obj


@app.tool()
def notion_update_status(
    page_id: str,
    status_property: str = "Status",
    status_value: str = "In Progress",
    property_type: str = "select",
) -> Dict[str, Any]:
    """Update a Notion page's status select property.

    Args:
        page_id: The Notion page ID to update.
        status_property: Name of the select property used to track status.
        status_value: New status (select option) value.
        property_type: Property schema to use when updating: "select" (default) or "status" for newer Notion databases.
    Returns:
        Dict with success flag and response status.
    """
    headers = _notion_headers()
    if not headers:
        return {"success": False, "error": "NOTION_MCP_TOKEN not set in environment"}

    def _alt_values(val: str) -> List[str]:
        alts = set()
        alts.add(val)
        if val.lower() == "not started":
            alts.update(["Not started", "Not Started"])
        elif val.lower() == "in progress":
            alts.update(["In progress", "In Progress"])
        elif val.lower() == "done":
            alts.update(["Done"])
        else:
            alts.add(val.title())
        return list(alts)

    def _payload(update_key: str, value: str) -> Dict[str, Any]:
        return {
            "properties": {
                status_property: {
                    update_key: {"name": value},
                }
            }
        }

    url = f"https://api.notion.com/v1/pages/{page_id}"
    with httpx.Client(timeout=30) as client:
        preferred_key = "select" if (property_type or "select").lower() == "select" else "status"
        fallback_key = "status" if preferred_key == "select" else "select"

        # Try preferred key first
        resp = client.patch(url, headers=headers, json=_payload(preferred_key, status_value))
        try:
            body: Dict[str, Any] = resp.json()
        except Exception:
            body = {"raw": resp.text}

        if resp.status_code != 200:
            # Try fallback key
            resp = client.patch(url, headers=headers, json=_payload(fallback_key, status_value))
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text}

        if resp.status_code != 200:
            # Try alternate capitalizations on both keys
            for v in _alt_values(status_value):
                resp = client.patch(url, headers=headers, json=_payload(preferred_key, v))
                try:
                    body = resp.json()
                except Exception:
                    body = {"raw": resp.text}
                if resp.status_code == 200:
                    break
            if resp.status_code != 200:
                for v in _alt_values(status_value):
                    resp = client.patch(url, headers=headers, json=_payload(fallback_key, v))
                    try:
                        body = resp.json()
                    except Exception:
                        body = {"raw": resp.text}
                    if resp.status_code == 200:
                        break

    return {"success": resp.status_code == 200, "status": resp.status_code, "data": body}


@app.tool()
def notion_get_database(database_id: str) -> Dict[str, Any]:
    """Retrieve a Notion database definition (schema and metadata).

    Args:
        database_id: The Notion database ID to fetch.
    Returns:
        Dict with success flag, status code, and raw Notion database JSON under `data`.
    """
    headers = _notion_headers()
    if not headers:
        return {"success": False, "error": "NOTION_MCP_TOKEN not set in environment"}

    url = f"https://api.notion.com/v1/databases/{database_id}"
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers=headers)
        try:
            body: Dict[str, Any] = resp.json()
        except Exception:
            body = {"raw": resp.text}

    return {"success": resp.status_code == 200, "status": resp.status_code, "data": body}


@app.tool()
def notion_update_database_schema(
    database_id: str,
    ensure_status: bool = True,
    status_property: str = "Status",
    status_values: Optional[List[str]] = None,
    add_output_properties: bool = False,
) -> Dict[str, Any]:
    """Update a Notion database schema to fit the pipeline.

    Operations performed:
    - Ensure a `Status` property exists (status or select) with values [Not Started, In Progress, Done].
    - Optionally add long-text output properties used by agents (for users who prefer properties).

    Note: Agents can also write large content as page blocks; properties are optional.

    Args:
        database_id: Target Notion database ID.
        ensure_status: When true, create/normalize the Status property and its options.
        status_property: Name of the status/select property to normalize.
        status_values: Custom list of status values; defaults to [Not Started, In Progress, Done].
        add_output_properties: When true, add rich text properties for outputs.
    Returns:
        Dict with success flag, status code, and Notion response body under `data`.
    """
    headers = _notion_headers()
    if not headers:
        return {"success": False, "error": "NOTION_MCP_TOKEN not set in environment"}

    # Defaults for status
    values = status_values or ["Not Started", "In Progress", "Done"]
    # Build option objects with sensible colors
    def _color_for(val: str) -> str:
        v = val.lower()
        if "not" in v:
            return "gray"
        if "progress" in v:
            return "yellow"
        if "done" in v or "complete" in v:
            return "green"
        return "default"

    status_options = [{"name": v, "color": _color_for(v)} for v in values]

    # Fetch current schema to decide how to patch
    url_get = f"https://api.notion.com/v1/databases/{database_id}"
    url_patch = url_get

    with httpx.Client(timeout=30) as client:
        get_resp = client.get(url_get, headers=headers)
        try:
            db_body: Dict[str, Any] = get_resp.json()
        except Exception:
            db_body = {"raw": get_resp.text}
        if get_resp.status_code != 200:
            return {"success": False, "status": get_resp.status_code, "data": db_body}

        properties: Dict[str, Any] = db_body.get("properties", {}) or {}

        patch: Dict[str, Any] = {"properties": {}}

        if ensure_status:
            prop = properties.get(status_property)
            if not prop:
                # Create a Status-type property named `status_property` (cannot set options via API)
                patch["properties"][status_property] = {"status": {}}
            else:
                ptype = prop.get("type")
                if ptype == "status":
                    # Notion does not allow updating status options via API; send empty status object
                    patch["properties"][status_property] = {"status": {}}
                elif ptype == "select":
                    # For select, options can be set/normalized
                    patch["properties"][status_property] = {"select": {"options": status_options}}
                else:
                    # Can't change types arbitrarily; add a parallel Status prop if needed
                    alt_name = f"{status_property} (status)"
                    if alt_name not in properties:
                        patch["properties"][alt_name] = {"status": {}}

        if add_output_properties:
            # Only add if not present. Use Rich text for flexibility.
            def _maybe_add(name: str):
                if name not in properties:
                    patch["properties"][name] = {"rich_text": {}}

            _maybe_add("Research Summary")
            _maybe_add("Citations")
            _maybe_add("Outline")
            _maybe_add("Draft")
            _maybe_add("Polished Script")
            _maybe_add("Segments")

        # If nothing to change, return early
        if not patch["properties"]:
            return {"success": True, "status": 200, "data": {"message": "No schema changes required"}}

        patch_resp = client.patch(url_patch, headers=headers, json=patch)
        try:
            patch_body: Dict[str, Any] = patch_resp.json()
        except Exception:
            patch_body = {"raw": patch_resp.text}

    return {"success": patch_resp.status_code == 200, "status": patch_resp.status_code, "data": patch_body}


@app.tool()
def notion_append_section(
    page_id: str,
    heading: str,
    content: str,
    heading_level: int = 2,
) -> Dict[str, Any]:
    """Append a section to a Notion page: a heading followed by paragraph blocks.

    Notes:
    - This performs a simple transformation: split content by double newlines into paragraphs.
    - For large content, Notion limits rich_text segment lengths; this function chunks long paragraphs.

    Args:
        page_id: The Notion page ID (target parent block).
        heading: Section heading text.
        content: Section body text (plain text; minimal formatting only).
        heading_level: 1, 2, or 3; default 2.
    Returns:
        Dict with success flag, status, and Notion response data.
    """
    headers = _notion_headers()
    if not headers:
        return {"success": False, "error": "NOTION_MCP_TOKEN not set in environment"}

    def _rt(text: str) -> List[Dict[str, Any]]:
        return [{"type": "text", "text": {"content": text[:2000]}}]

    # Build children: heading + paragraphs
    heading_level = max(1, min(3, int(heading_level or 2)))
    heading_key = {1: "heading_1", 2: "heading_2", 3: "heading_3"}[heading_level]

    children: List[Dict[str, Any]] = [
        {"object": "block", "type": heading_key, heading_key: {"rich_text": _rt(heading)}}
    ]

    # Split by blank lines to paragraphs
    paragraphs = [p.strip() for p in (content or "").split("\n\n") if p.strip()]
    for p in paragraphs:
        # Further chunk long paragraphs into ~1800-char segments
        start = 0
        while start < len(p):
            chunk = p[start:start+1800]
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": _rt(chunk)}
            })
            start += 1800

    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    with httpx.Client(timeout=30) as client:
        resp = client.patch(url, headers=headers, json={"children": children})
        try:
            body: Dict[str, Any] = resp.json()
        except Exception:
            body = {"raw": resp.text}

    return {"success": resp.status_code in (200, 202), "status": resp.status_code, "data": body}


if __name__ == "__main__":
    # Start FastMCP over stdio using the built-in transport handler
    app.run("stdio")
