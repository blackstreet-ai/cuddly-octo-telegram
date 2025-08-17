# ADK Multi‑Agent Scaffold

A minimal scaffold for a multi‑agent system using Google's Agent Development Kit (ADK).
MCP is optional and disabled by default.

## Features

- **Coordinator + Greeter + Executor** (`src/orchestration/coordinator.py`, `src/agents/`)
- **CLI app** with single‑shot and interactive modes (`src/app.py`)
- **Demo tools wired**: `math_eval`, `summarize`, `keyword_extract` (`src/tools/demo_tools.py`)
- **Optional MCP** helper with `${PROJECT_ROOT}` placeholder (`src/tools/mcp.py`)
- **Config‑driven** via `config/runconfig.yaml`

## Prerequisites

- Python 3.11+
- A Google AI Studio API key (or Vertex AI credentials)

## Setup

```bash
# Create and activate a Python 3.11 virtualenv
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Configure API credentials (choose one)
# Option A: Google AI Studio API key
echo "GOOGLE_API_KEY=YOUR_API_KEY" >> .env

# Option B: Vertex AI (ADC or service account)
# export VERTEXAI_PROJECT=your-project-id
# export VERTEXAI_LOCATION=us-central1
```

## Quickstart

- **Single‑shot**

  ```bash
  python -m src.app --task "Use the math tool to evaluate: (2 + 3) * 4."
  ```

- **Interactive chat**

  ```bash
  python -m src.app --interactive
  ```

- **Custom config path**

  ```bash
  python -m src.app --config config/runconfig.yaml --task "hello"
  ```

## Configuration

`config/runconfig.yaml` controls models and optional MCP. Example MCP block:

```yaml
mcp:
  enabled: false
  connection:
    type: stdio
    stdio:
      command: npx
      args:
        - "-y"
        - "@modelcontextprotocol/server-filesystem"
        - "${PROJECT_ROOT}"
      env: {}
  tool_filter: []
```

- `${PROJECT_ROOT}` is expanded at runtime to the repo root.
- To enable MCP set `enabled: true` and ensure Node + `npx` are installed.

## Testing

```bash
pytest -q
```

## Troubleshooting

- "Default value is not supported in function declaration schema" — benign warning from function tool schema generation.
- Ensure you are running with the project venv’s Python 3.11 (e.g., `source .venv/bin/activate`).

## First push to GitHub

Below are the typical steps for an initial push (replace placeholders):

```bash
git init
git add .
git commit -m "chore: initial commit"
git branch -M main
git remote add origin git@github.com:<YOUR_GH_USER>/<YOUR_REPO>.git
git push -u origin main
```

This repo includes a `.gitignore`. We do not write to your `.env`; use `.env.sample` as reference.
