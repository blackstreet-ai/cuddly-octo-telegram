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


def test_build_coordinator_sequential():
    cfg = {
        "coordinator": {"name": "coordinator"},
        # minimal single sub-agent so SequentialAgent has one child
        "research_summarizer": {
            "name": "research_summarizer",
            "model": "gemini-2.0-flash",
            "instruction": "summarize research",
        },
    }
    agent = build_coordinator(cfg, shared_tools=[])
    assert isinstance(agent, SequentialAgent)
    assert agent.name == "coordinator"
