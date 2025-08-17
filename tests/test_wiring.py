import os
import sys
import pytest

# Ensure project root on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from google.adk.agents import LlmAgent  # type: ignore
except Exception:
    pytest.skip("google-adk not installed; skipping wiring test", allow_module_level=True)

from src.orchestration.coordinator import build_coordinator


def test_build_coordinator():
    cfg = {
        "greeter": {"name": "greeter"},
        "executor": {"name": "executor"},
        "coordinator": {"name": "coordinator"},
    }
    agent = build_coordinator(cfg, extra_tools=[])
    assert isinstance(agent, LlmAgent)
    assert agent.name == "coordinator"
