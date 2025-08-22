import argparse
import asyncio
import logging
import os
import sys
from typing import Optional, Tuple

import yaml
from dotenv import load_dotenv

# ADK imports (ensure google-adk is installed)
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService

# Local imports
from src.orchestration.coordinator import build_coordinator
from src.tools.mcp import build_mcp_toolset_from_config, close_mcp_toolset_if_any
from src.tools.demo_tools import math_eval, summarize, keyword_extract

# Get project root
def project_root() -> str:
    return os.path.dirname(os.path.abspath(__file__ + "/.."))

# Load config from YAML file with ${PROJECT_ROOT} placeholder expansion
def load_config(path: str) -> dict:
    # Load environment variables from .env if present
    load_dotenv()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    # simple ${PROJECT_ROOT} placeholder expansion for strings
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    def expand(value):
        if isinstance(value, str):
            # Expand ${PROJECT_ROOT}
            expanded = value.replace("${PROJECT_ROOT}", root)
            # Expand ${ENV:VAR_NAME}
            if "${ENV:" in expanded:
                import re
                def repl(match):
                    var = match.group(1)
                    return os.environ.get(var, "")
                expanded = re.sub(r"\$\{ENV:([A-Z0-9_]+)\}", repl, expanded)
            return expanded
        if isinstance(value, list):
            return [expand(v) for v in value]
        if isinstance(value, dict):
            return {k: expand(v) for k, v in value.items()}
        return value
    return expand(data)

# Build system from config
async def build_system(cfg: dict) -> Tuple[LlmAgent, Optional[object]]:
    # Build optional MCP toolset from config (disabled by default)
    mcp_toolset = await build_mcp_toolset_from_config(cfg.get("mcp", {}))

    # Build coordinator
    # - shared_tools go to all sub-agents
    # - topic_tools (e.g., Notion MCP) go ONLY to topic_clarifier
    shared_tools = [math_eval, summarize, keyword_extract]
    topic_tools = [mcp_toolset] if mcp_toolset else []
    coordinator = build_coordinator(
        cfg.get("agents", {}),
        shared_tools=shared_tools,
        topic_tools=topic_tools,
    )

    # Wrap in Runner services
    return coordinator, mcp_toolset

# Run single-shot task
async def run_single_shot(cfg: dict, task: str) -> None:
    coordinator, mcp_toolset = await build_system(cfg)

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()

    runner = Runner(
        app_name=cfg.get("app_name", coordinator.name),
        agent=coordinator,
        artifact_service=artifact_service,
        session_service=session_service,
    )

    session = await session_service.create_session(state={}, app_name=runner.app_name, user_id="user")

    from google.genai import types
    content = types.Content(role='user', parts=[types.Part(text=task)])

    try:
        async for event in runner.run_async(session_id=session.id, user_id=session.user_id, new_message=content):
            # Log events at debug level
            logging.debug("EVENT: %s", event)
            # Print final response to stdout
            if event.is_final_response():
                parts = getattr(event.content, "parts", []) or []
                # Concatenate any text parts for display
                texts = [getattr(p, "text", "") for p in parts if hasattr(p, "text")]
                if texts:
                    print("\n=== Final Answer ===\n" + "\n".join(texts))
    finally:
        await close_mcp_toolset_if_any(mcp_toolset)

# Run interactive chat loop
async def run_interactive(cfg: dict) -> None:
    coordinator, mcp_toolset = await build_system(cfg)

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()

    runner = Runner(
        app_name=cfg.get("app_name", coordinator.name),
        agent=coordinator,
        artifact_service=artifact_service,
        session_service=session_service,
    )

    session = await session_service.create_session(state={}, app_name=runner.app_name, user_id="user")

    print("Interactive mode. Type 'exit' to quit.")
    try:
        while True:
            prompt = input("You> ").strip()
            if prompt.lower() in {"exit", "quit"}:
                break
            if not prompt:
                continue
            from google.genai import types
            content = types.Content(role='user', parts=[types.Part(text=prompt)])
            async for event in runner.run_async(session_id=session.id, user_id=session.user_id, new_message=content):
                logging.debug("EVENT: %s", event)
                if event.is_final_response():
                    parts = getattr(event.content, "parts", []) or []
                    texts = [getattr(p, "text", "") for p in parts if hasattr(p, "text")]
                    if texts:
                        print("Agent>", "\n".join(texts))
    finally:
        await close_mcp_toolset_if_any(mcp_toolset)

# Main entry point
def main() -> None:
    parser = argparse.ArgumentParser(description="ADK Multi-Agent Scaffold")
    parser.add_argument("--config", default="config/runconfig.yaml", help="Path to YAML run config")
    parser.add_argument("--task", default=None, help="Single-shot task text")
    parser.add_argument("--interactive", action="store_true", help="Run interactive chat loop")
    parser.add_argument("--log-level", default="INFO", help="Logging level")

    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")

    cfg = load_config(args.config)

    try:
        if args.interactive:
            asyncio.run(run_interactive(cfg))
        elif args.task:
            asyncio.run(run_single_shot(cfg, args.task))
        else:
            print("Provide --task or --interactive. Use --help for options.")
            sys.exit(2)
    except KeyboardInterrupt:
        print("\nInterrupted.")

# Run app
if __name__ == "__main__":
    main()
