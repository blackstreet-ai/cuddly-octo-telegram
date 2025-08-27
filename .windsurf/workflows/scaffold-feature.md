---
description: Scaffold a new feature (stage/tool) using the project template
auto_execution_mode: 3
---

This workflow helps you scaffold a new feature for the BSJ Script Writer, aligned with the repo's ADK pipeline, YAML-driven agent wiring, and MCP tooling. It leverages `docs/templates/feature-template.md`.

Prereqs:
- Python 3.11+, uv installed
- Dependencies synced (uv sync)
- .env configured as needed (GOOGLE_API_KEY, TAVILY_API_KEY, NOTION_MCP_TOKEN)

1) Review the feature template
- Open and skim `docs/templates/feature-template.md`.

2) Choose a feature key
- Decide a machine-friendly key for your feature, e.g. `evidence_curator` or `notion_ingestor`.

// turbo
3) Create a working branch
- Run:
```bash
git checkout -b feature/<your-key>
```

4) Create a docs stub from template
- Create a feature doc at `docs/features/<your-key>.md`.
- Suggested content: copy the template then fill Summary, Scope, Deliverables.

Example:
```bash
mkdir -p docs/features
cp docs/templates/feature-template.md docs/features/<your-key>.md
```

5) If adding a new pipeline stage
- Update `src/orchestration/coordinator.py` if the stage must be in fixed order:
  - Append your key to `pipeline_order` list.
- Add a YAML block to `config/runconfig.yaml` under `agents:`:

YAML skeleton:
```yaml
agents:
  <your-key>:
    model: gemini-2.5-flash
    name: <your-key>
    description: One-line role description.
    instruction: |
      Clear, testable instructions for this stage.
```

6) If adding or updating MCP tools
- For local tools: implement in `src/tools/local_mcp_server.py` using `@app.tool()`.
- Ensure `config/runconfig.yaml → mcp.enabled: true` and correct `connection.type` (stdio for local server).
- Optionally restrict tools with `mcp.tool_filter`.

Local MCP tool skeleton (reference only):
```python
from mcp.server.fastmcp import FastMCP
app = FastMCP("local-mcp-tools")

@app.tool()
def my_new_tool(arg1: str, limit: int = 5) -> dict:
    """Describe inputs/outputs clearly."""
    return {"ok": True, "items": []}
```

7) Add tests
- Create `tests/test_<your-key>.py`.
- For tools, mock network/IO and assert request/response structure.
- For wiring, assert coordinator and presence/order similar to `tests/test_wiring.py`.

Minimal wiring test example:
```python
from src.orchestration.coordinator import build_coordinator

def test_build_custom_stage():
    cfg = {
        "coordinator": {"name": "coordinator"},
        "<your-key>": {"name": "<your-key>", "model": "gemini-2.5-flash", "instruction": "do X"},
    }
    agent = build_coordinator(cfg, shared_tools=[])
    assert agent.name == "coordinator"
```

// turbo
8) Run tests
```bash
uv run pytest -q
```

9) Update docs
- In `README.md`, optionally link to your new `docs/features/<your-key>.md` under a new "Templates/Features" section.

// turbo
10) Commit
```bash
git add -A && git commit -m "feat: scaffold <your-key> feature (docs, config, tests)"
```

11) Push and open PR
- Use your existing workflow `/stage-commit-push` to push changes.
- Open a PR with a summary referencing your feature doc, config diffs, and test results.

12) Backout plan
- Revert changes to `config/runconfig.yaml` and code if needed.
- Remove or skip failing tests temporarily.
- Ensure baseline 5-stage pipeline still runs.