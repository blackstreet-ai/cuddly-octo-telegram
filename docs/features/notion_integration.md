# Feature: Notion Integration (topic_verifier)

This feature adds a Notion-driven intake stage to the ADK pipeline, making a Notion database the single source of truth for topic lifecycle.

- Pipeline Stage: `topic_verifier` (pre-stage before research)
- Tools: Local MCP Notion tools in `src/tools/local_mcp_server.py`
- Config: New agent block in `config/runconfig.yaml`
- Tests: Wiring and tool tests with mocked HTTP

## Summary
- Goal: Select eligible topics from a Notion database to kick off the pipeline.
- Scope: Pipeline stage + local MCP tool integration + tests + docs.
- Deliverables:
  - New agent `topic_verifier` wired into fixed order.
  - MCP tools: `notion_query_eligible`, `notion_update_status`.
  - Tests for wiring and tools.

## Details

### Stage Behavior (`topic_verifier`)
- Queries Notion for rows with `Status = "Not Started"`.
- Selects one row to process and may set it to `In Progress`.
- Outputs a compact JSON `{page_id, title, metadata}` for downstream stages.
 - Status lifecycle: `Not Started` → `In Progress` → `Done`.

### MCP Tools (local stdio)
Defined in `src/tools/local_mcp_server.py` using `FastMCP`:
- `notion_query_eligible(database_id=None, status_property="Status", status_value="Not Started", property_type="select", page_size=5)`
  - Calls `POST /v1/databases/{database_id}/query`
  - Returns minimal page list: `[{page_id, title, properties}]`.
  - If `database_id` is omitted, reads `NOTION_DATABASE_ID` from the environment.
  - property_type can be `select` (default) or `status` (Notion Status-type). The tool internally retries with the other type and common capitalization variants if the first attempt fails or yields zero results.
- `notion_update_status(page_id, status_property="Status", status_value="In Progress")`
  - Calls `PATCH /v1/pages/{page_id}`
  - Updates a select property to a new value.
  - Accepts `property_type` (default `select`). Internally retries with the other type and capitalization variants on failure.

Environment variables required:
- `NOTION_MCP_TOKEN` — Notion API token
- `NOTION_DATABASE_ID` — default database used when `database_id` arg is omitted

### Config
Add an agent block under `agents.topic_verifier` in `config/runconfig.yaml` (already added).
Coordinator fixed order updated in `src/orchestration/coordinator.py` to include `topic_verifier` and remain backward compatible with `topic_clarifier`.

End-of-pipeline behavior:
- The `social_segmenter` instruction includes an explicit step to call `notion_update_status` with `status_value: "Done"` when a `page_id` is available from `topic_verifier`.

### Testing
- `tests/test_topic_verifier_wiring.py`: asserts coordinator builds Sequential pipeline with `topic_verifier`.
- `tests/test_notion_tools.py`: unit tests Notion tools with mocked `httpx.Client`.

## Usage Notes
- Ensure `.env` has `NOTION_MCP_TOKEN`.
- `config/runconfig.yaml → mcp.enabled: true` and `connection.type: stdio` are already configured.

## Backout Plan
- Remove the `topic_verifier` block from YAML.
- Revert `coordinator.py` fixed order changes.
- Remove Notion MCP tools.
- Skip/remove tests.
