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

### MCP Tools (local stdio)
Defined in `src/tools/local_mcp_server.py` using `FastMCP`:
- `notion_query_eligible(database_id, status_property="Status", status_value="Not Started", page_size=5)`
  - Calls `POST /v1/databases/{database_id}/query`
  - Returns minimal page list: `[{page_id, title, properties}]`.
- `notion_update_status(page_id, status_property="Status", status_value="In Progress")`
  - Calls `PATCH /v1/pages/{page_id}`
  - Updates a select property to a new value.

Environment variable required: `NOTION_MCP_TOKEN`.

### Config
Add an agent block under `agents.topic_verifier` in `config/runconfig.yaml` (already added).
Coordinator fixed order updated in `src/orchestration/coordinator.py` to include `topic_verifier` and remain backward compatible with `topic_clarifier`.

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
