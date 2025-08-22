# BSJ Script Writer

A specialized multi-agent system for generating commentary scripts using Google's Agent Development Kit (ADK). Built for creating 900-1400 word scripts optimized for social media segments with a bold, culturally aware voice.

## Features

- **5-Stage Pipeline**: Research → Outline → Draft → Polish → Segment
- **Multi-Agent Architecture**: Coordinator orchestrates specialized sub-agents
- **Notion Integration**: Optional MCP connection for topic management
- **CLI Interface**: Single-shot and interactive modes
- **Configurable Models**: Uses Gemini 2.5 Pro/Flash for different stages
- **Social Media Ready**: Outputs optimized for Shorts/Reels/TikTok

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

# Configure API credentials
cp .env.sample .env
# Edit .env and add your Google AI Studio API key:
# GOOGLE_API_KEY=your_api_key_here

# Optional: Configure Notion integration
# NOTION_MCP_TOKEN=your_notion_integration_token
```

## Usage

### Generate Commentary Scripts

**Single-shot with parameters:**
```bash
python -m src.app --task "Generate a script about AI regulation using these parameters: topic='AI Safety Regulation', angle='Critical analysis of recent policy changes', stance='Cautiously optimistic but highlighting gaps', audience='Tech-aware general public'" --log-level INFO
```

**Interactive mode:**
```bash
python -m src.app --interactive --log-level INFO
```

**Auto-continue (no prompts between stages):**
```bash
# CLI flag (overridden by YAML if set)
python -m src.app --task "Generate a commentary script on climate policy" --auto-continue --log-level INFO
```
You can also set `pipeline.auto_continue: true` in `config/runconfig.yaml` (config takes precedence over CLI).

**General topic (system extracts parameters):**
```bash
python -m src.app --task "Generate a commentary script on climate policy" --log-level INFO
```

### Pipeline Stages

The system executes a 5-stage pipeline:

1. **Research** - Gathers 3-7 high-quality sources
2. **Outline** - Creates 6-part structure (Hook, Background, Core Argument, Evidence, Counterpoints, Closer)
3. **Draft** - Writes 900-1400 words in bold, serious, culturally fluent tone
4. **Polish** - Refines for performance with pacing cues and emphasis markers
5. **Segment** - Splits into 4-8 social media segments (~60 seconds each)

### Outputs & Files

- **Directory**: Files are saved under `./pipeline_outputs/` when enabled.
- **Formats**: Controlled by `output.formats` in `config/runconfig.yaml` (supports `json`, `markdown`).
- **Intermediate saves**: When `output.save_intermediate_steps: true`, each streamed event and each stage's final output are written to disk.
- **Semantic filenames**: Filenames are prefixed by the stage:
  - `01_research_*`, `02_outline_*`, `03_draft_*`, `04_polish_*`, `05_segment_*`
  Examples: `01_research_event_00.md`, `03_draft_final.json`.

Markdown files contain the extracted text. JSON files contain safe metadata (event type, author, is_final, text) for easier debugging.

## Configuration

### Agent Models

The system uses different Gemini models for optimal performance:
- **Coordinator**: `gemini-2.5-pro` (complex orchestration)
- **Sub-agents**: `gemini-2.5-flash` (specialized tasks)

### Run-time Controls (YAML)

Set these in `config/runconfig.yaml`:

```yaml
logging:
  level: DEBUG            # DEBUG | INFO | WARNING | ERROR
  show_intermediate_outputs: false  # true to print each step to console

output:
  save_intermediate_steps: true     # save streamed outputs
  output_dir: "./pipeline_outputs"   # where files are written
  formats: ["json", "markdown"]     # file formats to emit

pipeline:
  auto_continue: true               # run all stages without prompts
```

Notes:
- Config settings take precedence over CLI flags (e.g., `pipeline.auto_continue`).
- To reduce console noise but keep files, set `show_intermediate_outputs: false` and keep `save_intermediate_steps: true`.

### Notion Integration (Optional)

To enable Notion topic management:

1. Create a Notion integration at https://www.notion.so/profile/integrations
2. Add the integration to your database page
3. Set `NOTION_MCP_TOKEN` in your `.env` file
4. Enable MCP in `config/runconfig.yaml`:

```yaml
mcp:
  enabled: true
  connection:
    type: stdio
    stdio:
      command: npx
      args: ["-y", "@notionhq/notion-mcp-server"]
      env:
        NOTION_TOKEN: "your_notion_token_here"
```

## Testing

Test Notion connection:
```bash
python test_notion.py
```

Run unit tests:
```bash
pytest -q
```

## Troubleshooting

- **"Default value is not supported"** — Benign warning from function schema generation
- **"API token is invalid"** — Check your Notion integration token and permissions
- **"Context variable not found"** — Ensure pipeline stages don't reference undefined variables
- **Virtual environment** — Always activate: `source .venv/bin/activate`
- **"Tool or function not found (e.g., search)"** — Ensure required tools are registered/enabled in config. If you disabled MCP or external tools, the Research stage may fail. Re-enable the relevant tool integration or adjust the Research instruction to avoid external calls.

## Architecture

```
BSJ Script Writer
├── Coordinator (gemini-2.5-pro)
│   ├── Research Summarizer (gemini-2.5-flash)
│   ├── Outline Organizer (gemini-2.5-flash)
│   ├── Draft Generator (gemini-2.5-flash)
│   ├── Narration Polisher (gemini-2.5-flash)
│   └── Social Segmenter (gemini-2.5-flash)
└── Optional: Notion MCP Integration
```
