import os
import sys
import pytest

# Ensure project root on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from google.adk.agents import SequentialAgent  # type: ignore
except Exception:
    pytest.skip("google-adk not installed; skipping wiring test", allow_module_level=True)

from src.orchestration.coordinator import build_coordinator


def test_build_with_topic_verifier_stage():
    cfg = {
        "coordinator": {"name": "coordinator"},
        "topic_verifier": {
            "name": "topic_verifier",
            "model": "gemini-2.5-flash",
            "instruction": "verify topics from notion",
        },
        # Add a second stage so SequentialAgent has >1 sub-agent
        "research_summarizer": {
            "name": "research_summarizer",
            "model": "gemini-2.5-flash",
            "instruction": "summarize research",
        },
    }

    # No special tools required for this smoke test; ensure build doesn't require concrete tool objects
    agent = build_coordinator(cfg, shared_tools=[], topic_tools=[])
    assert isinstance(agent, SequentialAgent)
    assert agent.name == "coordinator"
