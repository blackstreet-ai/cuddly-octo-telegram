from typing import List

from google.adk.agents import LlmAgent


def build_executor(cfg: dict, extra_tools: List[object]) -> LlmAgent:
    """Executor agent that performs tasks and can use tools.

    extra_tools: list of tool instances to attach (e.g., MCPToolset)
    """
    return LlmAgent(
        model=cfg.get("model", "gemini-2.0-flash"),
        name=cfg.get("name", "executor"),
        description=cfg.get("description", "Executes tasks and uses tools to get results."),
        instruction=cfg.get(
            "instruction",
            (
                "You execute the user's task. If tools are available, use them appropriately. "
                "Provide a concise final answer and include any important details."
            ),
        ),
        tools=extra_tools or [],
    )
