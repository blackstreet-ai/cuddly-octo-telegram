"""
Local MCP server (stdio) exposing simple, reliable tools for the agents.

Tools provided:
- http_fetch(url: str) -> {status, headers, text}
- extract_text(html: str) -> {text}
- tavily_search(...) -> Tavily web search response summary

Implementation uses the MCP Python library's FastMCP helper for a minimal server
that communicates over stdio. The app will spawn this as a subprocess when
configured with connection.type=stdio in config/runconfig.yaml.
"""

from __future__ import annotations

import os
import re
import time
import random
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv


# Load variables from .env so subprocess has access to keys like TAVILY_API_KEY, NOTION_MCP_TOKEN
load_dotenv()

app = FastMCP("local-mcp-tools")


# Simple HTTP retry helper for Notion API (handles 429 with backoff)
def _request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
    max_retries: Optional[int] = None,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
) -> httpx.Response:
    attempt = 0
    # Allow environment to override defaults
    if max_retries is None:
        try:
            max_retries = int(os.getenv("NOTION_MAX_RETRIES", "5"))
        except Exception:
            max_retries = 5
    if base_delay is None:
        try:
            base_delay = float(os.getenv("NOTION_BASE_DELAY", "0.6"))
        except Exception:
            base_delay = 0.6
    if max_delay is None:
        try:
            max_delay = float(os.getenv("NOTION_MAX_DELAY", "8.0"))
        except Exception:
            max_delay = 8.0
    while True:
        resp = client.request(method.upper(), url, headers=headers, json=json)
        if resp.status_code != 429 or attempt >= max_retries:
            return resp
        # Respect Retry-After if present (seconds)
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                delay = float(retry_after)
            except Exception:
                delay = base_delay
        else:
            # Exponential backoff with jitter
            delay = min(max_delay, base_delay * (2 ** attempt))
            delay = delay * (0.8 + 0.4 * random.random())
        time.sleep(delay)
        attempt += 1


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


# Firecrawl tool removed by request; Tavily remains the supported search tool.


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
        resp = _request_with_retry(client, "POST", url, headers=headers, json=_build_payload(filter_key, value))
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
        resp = _request_with_retry(client, "PATCH", url, headers=headers, json=_payload(preferred_key, status_value))
        try:
            body: Dict[str, Any] = resp.json()
        except Exception:
            body = {"raw": resp.text}

        if resp.status_code != 200:
            # Try fallback key
            resp = _request_with_retry(client, "PATCH", url, headers=headers, json=_payload(fallback_key, status_value))
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text}

        if resp.status_code != 200:
            # Try alternate capitalizations on both keys
            for v in _alt_values(status_value):
                resp = _request_with_retry(client, "PATCH", url, headers=headers, json=_payload(preferred_key, v))
                try:
                    body = resp.json()
                except Exception:
                    body = {"raw": resp.text}
                if resp.status_code == 200:
                    break
            if resp.status_code != 200:
                for v in _alt_values(status_value):
                    resp = _request_with_retry(client, "PATCH", url, headers=headers, json=_payload(fallback_key, v))
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
        resp = _request_with_retry(client, "GET", url, headers=headers)
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
        get_resp = _request_with_retry(client, "GET", url_get, headers=headers)
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

        patch_resp = _request_with_retry(client, "PATCH", url_patch, headers=headers, json=patch)
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
    detect_lists: bool = True,
    find_existing: bool = True,
    mode: str = "append",
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
        detect_lists: When true, convert lines starting with "- ", "* ", or "1. " into list items.
        find_existing: When true, append under an existing heading with the same text if present.
        mode: "append" (default) to append after the heading, or "replace" to delete existing blocks
              between this heading and the next heading before appending fresh content.
    Returns:
        Dict with success flag, status, and Notion response data.
    """
    headers = _notion_headers()
    if not headers:
        return {"success": False, "error": "NOTION_MCP_TOKEN not set in environment"}

    def _rt(text: str) -> List[Dict[str, Any]]:
        """Convert plain text with simple inline markdown to Notion rich_text.

        Supported spans:
        - `code`
        - **bold**
        - *italic* or _italic_

        Notes:
        - This is a lightweight tokenizer; it does not handle complex nesting.
        - Each Notion text segment is chunked to <= 2000 chars preserving annotations.
        """
        import re as _re

        def _mk_segment(txt: str, bold: bool = False, italic: bool = False, code: bool = False) -> Dict[str, Any]:
            return {
                "type": "text",
                "text": {"content": txt},
                "annotations": {"bold": bool(bold), "italic": bool(italic), "code": bool(code)},
            }

        # Split into tokens: code, bold, italic, or plain
        pattern = _re.compile(r"(`[^`]+`|\*\*[^*]+\*\*|\*[^*\n]+\*|_[^_\n]+_)")
        tokens: List[Dict[str, Any]] = []

        idx = 0
        for m in pattern.finditer(text or ""):
            if m.start() > idx:
                plain = (text or "")[idx : m.start()]
                if plain:
                    tokens.append(_mk_segment(plain))
            span = m.group(0)
            if span.startswith("`") and span.endswith("`"):
                inner = span[1:-1]
                tokens.append(_mk_segment(inner, code=True))
            elif span.startswith("**") and span.endswith("**"):
                inner = span[2:-2]
                tokens.append(_mk_segment(inner, bold=True))
            elif span.startswith("*") and span.endswith("*"):
                inner = span[1:-1]
                tokens.append(_mk_segment(inner, italic=True))
            elif span.startswith("_") and span.endswith("_"):
                inner = span[1:-1]
                tokens.append(_mk_segment(inner, italic=True))
            idx = m.end()
        # Trailing plain text
        if (text or "") and idx < len(text):
            trailing = text[idx:]
            if trailing:
                tokens.append(_mk_segment(trailing))

        # Chunk segments to 2000 chars to satisfy Notion limits
        chunked: List[Dict[str, Any]] = []
        for t in tokens or [_mk_segment("")]:
            content = t["text"]["content"]
            bold = t.get("annotations", {}).get("bold", False)
            italic = t.get("annotations", {}).get("italic", False)
            code = t.get("annotations", {}).get("code", False)
            if len(content) <= 2000:
                chunked.append(t)
            else:
                for i in range(0, len(content), 2000):
                    chunked.append(_mk_segment(content[i : i + 2000], bold=bold, italic=italic, code=code))
        return chunked

    # Build children: heading + parsed body blocks
    heading_level = max(1, min(3, int(heading_level or 2)))
    heading_key = {1: "heading_1", 2: "heading_2", 3: "heading_3"}[heading_level]

    # Optionally find an existing heading and insert after it
    after_block_id: Optional[str] = None
    created_heading = False

    def _paragraph_block(text: str) -> Dict[str, Any]:
        return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rt(text)}}

    def _bullet_block(text: str) -> Dict[str, Any]:
        return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": _rt(text)}}

    def _numbered_block(text: str) -> Dict[str, Any]:
        return {"object": "block", "type": "numbered_list_item", "numbered_list_item": {"rich_text": _rt(text)}}

    body_blocks: List[Dict[str, Any]] = []

    import re
    lines = (content or "").splitlines()

    # Determine indent size (spaces per level) from the content, default to 2
    indent_candidates: List[int] = []
    list_pat_bullet = re.compile(r"^(?P<indent>\s*)(?:[-*])\s+(?P<text>.+)$")
    list_pat_number = re.compile(r"^(?P<indent>\s*)\d+[\.)]\s+(?P<text>.+)$")
    for l in lines:
        m = list_pat_bullet.match(l) or list_pat_number.match(l)
        if m:
            ind = len(m.group("indent") or "")
            if ind > 0:
                indent_candidates.append(ind)
    indent_size = min(indent_candidates) if indent_candidates else 2

    def _make_block(kind: str, text: str) -> Dict[str, Any]:
        if kind == "bullet":
            return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": _rt(text)}, "children": []}
        else:
            return {"object": "block", "type": "numbered_list_item", "numbered_list_item": {"rich_text": _rt(text)}, "children": []}

    para_buf: List[str] = []
    list_stack: List[tuple[int, Dict[str, Any]]] = []  # (level, block)

    def _flush_paragraph():
        nonlocal para_buf, body_blocks, list_stack
        if not para_buf:
            return
        p = " ".join(para_buf).strip()
        if p:
            for i in range(0, len(p), 1800):
                body_blocks.append(_paragraph_block(p[i:i + 1800]))
        para_buf = []
        # A paragraph ends any active list context for our simple parser
        list_stack = []

    for raw in lines + [""]:
        line = raw.rstrip("\n")
        # Handle list items with optional indentation
        if detect_lists:
            mb = list_pat_bullet.match(line)
            mn = list_pat_number.match(line)
            if mb or mn:
                _flush_paragraph()
                text = (mb or mn).group("text").strip()
                spaces = len((mb or mn).group("indent") or "")
                level = spaces // max(1, indent_size)
                kind = "bullet" if mb else "number"
                block = _make_block("bullet" if mb else "number", text)

                # Find correct parent by unwinding to the right level
                while list_stack and list_stack[-1][0] >= level:
                    list_stack.pop()
                if list_stack:
                    parent = list_stack[-1][1]
                    parent.setdefault("children", []).append(block)
                else:
                    body_blocks.append(block)
                list_stack.append((level, block))
                continue

        if line.strip() == "":
            # Blank line flushes paragraph
            _flush_paragraph()
        else:
            # Normal paragraph text
            para_buf.append(line)

    with httpx.Client(timeout=30) as client:
        if find_existing:
            # Search existing children for the heading
            get_url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
            gr = _request_with_retry(client, "GET", get_url, headers=headers)
            try:
                children_list = gr.json().get("results", [])
            except Exception:
                children_list = []
            for blk in children_list:
                if blk.get("type") == heading_key:
                    rt = (blk.get(heading_key) or {}).get("rich_text") or []
                    txt = "".join([(t.get("plain_text") or t.get("text", {}).get("content") or "") for t in rt])
                    if (txt or "").strip() == (heading or "").strip():
                        after_block_id = blk.get("id")
                        break

        # If no existing heading found, create it first under page
        if after_block_id is None:
            created_heading = True
            heading_block = {"object": "block", "type": heading_key, heading_key: {"rich_text": _rt(heading)}}
            create_url = f"https://api.notion.com/v1/blocks/{page_id}/children"
            cr = _request_with_retry(client, "PATCH", create_url, headers=headers, json={"children": [heading_block]})
            try:
                created = cr.json().get("results", [])
            except Exception:
                created = []
            # On success, use the new heading as parent
            if created:
                after_block_id = created[0].get("id")

        # If replace mode, delete existing blocks after the heading up to the next heading
        if mode and str(mode).lower() == "replace" and after_block_id:
            # Gather all children to find the range to delete
            # We need the parent page's direct children to determine sequence
            list_url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
            all_children: List[Dict[str, Any]] = []
            next_cursor: Optional[str] = None
            while True:
                url_q = list_url + (f"&start_cursor={next_cursor}" if next_cursor else "")
                lr = _request_with_retry(client, "GET", url_q, headers=headers)
                try:
                    payload = lr.json()
                except Exception:
                    payload = {"results": []}
                all_children.extend(payload.get("results", []) or [])
                if not payload.get("has_more"):
                    break
                next_cursor = payload.get("next_cursor")

            # Find index of our heading and next heading
            idx_heading = None
            for i, blk in enumerate(all_children):
                if blk.get("id") == after_block_id:
                    idx_heading = i
                    break
            if idx_heading is not None:
                next_heading_idx = None
                for j in range(idx_heading + 1, len(all_children)):
                    t = all_children[j].get("type")
                    if t in ("heading_1", "heading_2", "heading_3"):
                        next_heading_idx = j
                        break
                # Determine slice to delete: from idx_heading+1 up to next_heading_idx (exclusive) or to end
                delete_slice = all_children[idx_heading + 1 : (next_heading_idx if next_heading_idx is not None else len(all_children))]
                for blk in delete_slice:
                    bid = blk.get("id")
                    if not bid:
                        continue
                    del_url = f"https://api.notion.com/v1/blocks/{bid}"
                    _request_with_retry(client, "DELETE", del_url, headers=headers)

        # Append body blocks to the page, positioned right after the heading
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"

        def _sanitize(block: Dict[str, Any]) -> Dict[str, Any]:
            """Ensure block has correct structure and drop empty children arrays."""
            t = block.get("type")
            # map of required key for type
            req = {
                "paragraph": "paragraph",
                "bulleted_list_item": "bulleted_list_item",
                "numbered_list_item": "numbered_list_item",
                "heading_1": "heading_1",
                "heading_2": "heading_2",
                "heading_3": "heading_3",
            }
            if t in req and req[t] not in block:
                # If missing, convert to paragraph as a fallback
                text = ""
                if t in ("bulleted_list_item", "numbered_list_item"):
                    # try to recover text from wrong key
                    other = block.get("bulleted_list_item") or block.get("numbered_list_item") or {}
                    r = other.get("rich_text") or []
                    text = "".join([seg.get("text", {}).get("content", "") for seg in r])
                elif t.startswith("heading_"):
                    other = block.get(t) or {}
                    r = other.get("rich_text") or []
                    text = "".join([seg.get("text", {}).get("content", "") for seg in r])
                else:
                    other = block.get("paragraph") or {}
                    r = other.get("rich_text") or []
                    text = "".join([seg.get("text", {}).get("content", "") for seg in r])
                block = {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rt(text)}}
                t = "paragraph"
            # Recurse children
            ch = block.get("children")
            if isinstance(ch, list):
                new_children = []
                for c in ch:
                    sc = _sanitize(c)
                    # Drop if becomes empty paragraph
                    if sc.get("type") != "paragraph" or sc.get("paragraph", {}).get("rich_text"):
                        new_children.append(sc)
                if new_children:
                    block["children"] = new_children
                else:
                    block.pop("children", None)
            return block

        # Sanitize and batch
        sanitized = [_sanitize(b) for b in (body_blocks or [_paragraph_block("")])]
        results_body: Dict[str, Any] = {"results": []}
        # Notion recommends keeping request size modest; batch by 50
        for i in range(0, len(sanitized), 50):
            batch = sanitized[i : i + 50]
            payload: Dict[str, Any] = {"children": batch}
            if after_block_id:
                payload["after"] = after_block_id
                # After first insert, subsequent inserts should go after the last inserted block
            resp = _request_with_retry(client, "PATCH", url, headers=headers, json=payload)
            try:
                bpart: Dict[str, Any] = resp.json()
            except Exception:
                bpart = {"raw": resp.text}
            # Update after_block_id to last inserted block id if available
            try:
                inserted = bpart.get("results", [])
                if inserted:
                    after_block_id = inserted[-1].get("id", after_block_id)
                results_body.setdefault("batches", []).append(bpart)
            except Exception:
                pass
        body = results_body

    return {
        "success": resp.status_code in (200, 202),
        "status": resp.status_code,
        "data": body,
        "appended_under_existing": (not created_heading and after_block_id is not None),
    }


if __name__ == "__main__":
    # Start FastMCP over stdio using the built-in transport handler
    app.run("stdio")
