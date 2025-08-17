from typing import List, Optional

from google.adk.agents import LlmAgent

from src.agents.greeter import build_greeter
from src.agents.executor import build_executor


def build_coordinator(agents_cfg: dict, extra_tools: Optional[List[object]] = None) -> LlmAgent:
    """
    Compose a simple coordinator with two sub-agents: greeter and executor.
    extra_tools (e.g., MCPToolset) are attached to the executor so it can call them.
    """
    greeter = build_greeter(agents_cfg.get("greeter", {}))
    executor = build_executor(agents_cfg.get("executor", {}), extra_tools=extra_tools or [])

    coordinator_cfg = agents_cfg.get("coordinator", {})

    coordinator = LlmAgent(
        model=coordinator_cfg.get("model", "gemini-2.0-flash"),
        name=coordinator_cfg.get("name", "coordinator"),
        description=coordinator_cfg.get("description", "Coordinates greeting and task execution."),
        instruction=coordinator_cfg.get(
            "instruction",
            (
                "You are a coordinator. If the user needs greeting/clarification, "
                "delegate to greeter. If the task is clear, delegate to executor. "
                "Use sub_agents appropriately."
            ),
        ),
        sub_agents=[greeter, executor],
    )
    return coordinator
