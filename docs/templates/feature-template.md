# Project-Specific Feature Task Template (BSJ Script Writer)

Use this template to add features consistently to this ADK-based multi-agent pipeline. It’s tailored to the repo structure and conventions in:
- `src/orchestration/coordinator.py`
- `config/runconfig.yaml`
- `src/tools/` (`mcp.py`, `local_mcp_server.py`)
- `tests/` (`test_wiring.py`, `test_firecrawl_search.py`, `test_notion.py`)
- `README.md`, `pyproject.toml`

The coordinator supports both legacy “greeter/executor” and the pipeline stages:
- Current pipeline in docs: 5-stage (Research → Outline → Draft → Polish → Segment) per `README.md`.
- Coordinator supports optional 6th pre-stage `topic_clarifier` per `src/orchestration/coordinator.py`.

---

## 1) Feature Summary

- Goal:
- Scope: [Pipeline stage | Tool | MCP integration | Config | Docs | Tests]
- Success Criteria/Deliverables:
- Risk/Assumptions:
- Owner/ETA:

---

## 2) Pre-flight Checklist

- Environment ready with uv and Python 3.11+.
- `.env` updated for required keys (e.g., `GOOGLE_API_KEY`, `FIRECRAWL_API_KEY`, `NOTION_MCP_TOKEN`).
- Dependencies synced:
  - `uv sync`
- Test baseline:
  - `uv run pytest -q`

---

## 3) Pipeline/Agent Changes

- If adding/updating a stage, update `config/runconfig.yaml` under `agents:` with a new block.
  - Coordinator reads this config dynamically via `_build_llm_agent_from_cfg()` in `src/orchestration/coordinator.py`.
  - The fixed order used (when present): `topic_clarifier`, `research_summarizer`, `outline_organizer`, `draft_generator`, `narration_polisher`, `social_segmenter`.

YAML template for a new stage:

```yaml
agents:
  # ...
  new_stage_key:
    model: gemini-2.5-flash
    name: new_stage_key
    description: One-line role description.
    instruction: |
      Clear, testable instructions for this stage.
```

- If you need special tooling only for `topic_clarifier`, use `topic_tools` when building/wiring; coordinator already attaches `topic_tools` to `topic_clarifier` only.
- If you need tools shared by all stages, pass them as `shared_tools`.

---

## 4) Tooling & MCP

- For remote SSE MCP (e.g., Firecrawl), configure `config/runconfig.yaml → mcp.connection`.
- For local, privacy-friendly stdio tools, use `src/tools/local_mcp_server.py` and set `connection.type: stdio`.

Add a new local MCP tool (Python skeleton in `src/tools/local_mcp_server.py`):

```python
from mcp.server.fastmcp import FastMCP
app = FastMCP("local-mcp-tools")

@app.tool()
def my_new_tool(arg1: str, limit: int = 5) -> dict:
    """
    Brief docstring describing inputs/outputs.
    """
    # implement, return JSON-serializable dict
    return {"ok": True, "items": []}
```

If you need to construct MCP toolsets in-app (beyond local server), use/extend `src/tools/mcp.py → build_mcp_toolset_from_config()` or pass a tool filter in YAML:

```yaml
mcp:
  enabled: true
  tool_filter:
    - "firecrawl_search"
```

---

## 5) Wiring

- Coordinator auto-builds pipeline agents from `config/runconfig.yaml` via `build_coordinator()` in `src/orchestration/coordinator.py`.
- Typically no code changes are required for wiring unless:
  - You add a brand new stage key that must participate in the fixed order (update `pipeline_order` list).
  - You need special-case tool injection beyond existing `shared_tools`/`topic_tools` behavior.

If adding a new fixed-order stage, update:
- `src/orchestration/coordinator.py`: append your `new_stage_key` to `pipeline_order`.

---

## 6) Tests

- Unit test tools:
  - Follow `tests/test_firecrawl_search.py`. Mock network clients, assert request structure and response shape.
- Wiring tests:
  - Follow `tests/test_wiring.py` to assert coordinator type and sub-agent presence.
- External service tests:
  - Follow `tests/test_notion.py` for live-token checks (mark or skip as needed in CI).

Test checklist:
- Add `tests/test_<your_feature>.py`.
- Cover success and failure/error paths.
- Ensure tests pass without network unless explicitly intended (use monkeypatch/mocks).

Run:
- `uv run pytest -q`

---

## 7) Config & Docs

- Update `config/runconfig.yaml` with new stage/tool settings.
- Update `README.md`:
  - Features list and/or Pipeline Stages section.
  - Configuration instructions (YAML snippets).
  - Usage examples if CLI surface changes.

---

## 8) Validation

- Local run smoke test:
  - `python -m src.app --task "Generate a commentary script on X" --log-level INFO`
- If relying on MCP:
  - Ensure `mcp.enabled: true` and correct `connection.type` in `config/runconfig.yaml`.
  - For Firecrawl: verify `FIRECRAWL_API_KEY` set and `firecrawl_search` returns data.
- Verify output files (if enabled):
  - Check `./pipeline_outputs/` naming and formats per `README.md`.

---

## 9) Versioning & PR

- If new deps added, update `pyproject.toml` and re-run:
  - `uv sync`
- If needed for compatibility workflows:
  - `uv export --format requirements-txt --output requirements.txt`
- Open a PR with:
  - Summary of changes
  - Config diffs
  - Test results
  - Any required environment keys

---

## 10) Backout Plan

- Revert YAML stage block or tool config changes.
- Remove or skip failing tests temporarily.
- Confirm baseline pipeline (5-stage) still runs.

---

# Quick-Start Recipes

- Add a new fixed-order pipeline stage:
  1) Edit `src/orchestration/coordinator.py`: add `new_stage_key` to `pipeline_order`.
  2) Add YAML block under `agents.new_stage_key` in `config/runconfig.yaml`.
  3) Add tests in `tests/test_<new_stage>.py` (construct config, build coordinator, assert sequence).
  4) Update `README.md` Pipeline Stages.

- Add a new local MCP tool:
  1) Implement in `src/tools/local_mcp_server.py` with `@app.tool()`.
  2) Ensure `config/runconfig.yaml → mcp.connection.type: stdio` uses the local server.
  3) Unit test the tool (mock external I/O).
  4) Wire to stages via `shared_tools` or `topic_tools` if needed.

- Switch between SSE and stdio MCP:
  - Update `config/runconfig.yaml → mcp.connection.type` and matching block (`stdio` vs `sse`).
  - Keep `tool_filter` minimal and explicit if restricting tools.

---

Last updated: 2025-08-23
