from typing import List, Optional

from google.adk.agents import LlmAgent

from src.agents.greeter import build_greeter
from src.agents.executor import build_executor


def _build_llm_agent_from_cfg(cfg: dict, extra_tools: Optional[List[object]] = None) -> LlmAgent:
    """Construct a generic LlmAgent from a config dict.

    This allows us to support arbitrary sub-agent definitions in runconfig.yaml
    without needing a bespoke builder per agent, while keeping backwards
    compatibility with existing greeter/executor helpers.
    """
    return LlmAgent(
        model=cfg.get("model", "gemini-2.0-flash"),
        name=cfg.get("name", "agent"),
        description=cfg.get("description", ""),
        instruction=cfg.get("instruction", ""),
        tools=extra_tools or [],
    )


# Build coordinator from config
def build_coordinator(
    agents_cfg: dict,
    shared_tools: Optional[List[object]] = None,
    topic_tools: Optional[List[object]] = None,
    # Back-compat alias: if provided positionally or by name, treat as shared_tools
    extra_tools: Optional[List[object]] = None,
) -> LlmAgent:
    """
    Build a coordinator agent and its sub-agents from config.

    Backwards compatible behavior:
    - If `greeter` and `executor` configs are present, we build those using the
      dedicated builders and attach `extra_tools` to the executor only (legacy behavior).

    Extended behavior:
    - If pipeline-style agents (e.g., topic_clarifier, research_summarizer, outline_organizer,
      draft_generator, narration_polisher, social_segmenter) are present, we will build them
      in that fixed order when found and attach `extra_tools` to each sub-agent.
    - Otherwise, we will build any remaining agent entries (except `coordinator`) in
      dictionary order and attach `extra_tools` to each.
    """
    coordinator_cfg = agents_cfg.get("coordinator", {})

    # Map legacy extra_tools to shared_tools if shared_tools not explicitly provided
    if shared_tools is None and extra_tools is not None:
        shared_tools = extra_tools

    sub_agents: List[LlmAgent] = []

    has_greeter = "greeter" in agents_cfg
    has_executor = "executor" in agents_cfg

    if has_greeter and has_executor:
        # Legacy wiring path
        greeter = build_greeter(agents_cfg.get("greeter", {}))
        executor = build_executor(agents_cfg.get("executor", {}), extra_tools=shared_tools or [])
        sub_agents = [greeter, executor]
    else:
        # Pipeline-aware wiring path
        pipeline_order = [
            "topic_clarifier",
            "research_summarizer",
            "outline_organizer",
            "draft_generator",
            "narration_polisher",
            "social_segmenter",
        ]

        used_keys = set(["coordinator"])  # always exclude coordinator

        # Add known pipeline agents in fixed order when present
        for key in pipeline_order:
            if key in agents_cfg:
                agent_cfg = agents_cfg.get(key, {})
                # Attach shared tools to all; add topic_tools only to topic_clarifier
                tools_for_agent: List[object] = []
                if shared_tools:
                    tools_for_agent.extend(shared_tools)
                if key == "topic_clarifier" and topic_tools:
                    tools_for_agent.extend(topic_tools)
                sub_agents.append(_build_llm_agent_from_cfg(agent_cfg, extra_tools=tools_for_agent))
                used_keys.add(key)

        # Add any remaining custom agents (non-coordinator) in dict order
        for key, agent_cfg in agents_cfg.items():
            if key in used_keys:
                continue
            # Skip empty or non-dict entries just in case
            if not isinstance(agent_cfg, dict):
                continue
            tools_for_agent = list(shared_tools or [])
            if key == "topic_clarifier" and topic_tools:
                tools_for_agent.extend(topic_tools)
            sub_agents.append(_build_llm_agent_from_cfg(agent_cfg, extra_tools=tools_for_agent))
            used_keys.add(key)

    # Fallback: ensure at least one sub-agent exists to avoid runtime issues
    if not sub_agents:
        # As an ultra-conservative fallback, build a single generic executor from coordinator's defaults
        sub_agents = [
            _build_llm_agent_from_cfg(
                {
                    "model": coordinator_cfg.get("model", "gemini-2.0-flash"),
                    "name": "executor",
                    "description": "Generic executor",
                    "instruction": "Execute the user's task succinctly.",
                },
                extra_tools=shared_tools,
            )
        ]

    # Attach topic_tools (Notion MCP) to the coordinator itself since topic_clarifier is removed
    coordinator_tools: List[object] = []
    if topic_tools:
        coordinator_tools.extend(topic_tools)
    
    coordinator = LlmAgent(
        model=coordinator_cfg.get("model", "gemini-2.0-flash"),
        name=coordinator_cfg.get("name", "coordinator"),
        description=coordinator_cfg.get(
            "description",
            "Coordinates greeting and task execution.",
        ),
        instruction=coordinator_cfg.get(
            "instruction",
            (
                "You are a coordinator. If the user needs greeting/clarification, "
                "delegate to greeter. If the task is clear, delegate to executor. "
                "Use sub_agents appropriately."
            ),
        ),
        tools=coordinator_tools,
        sub_agents=sub_agents,
    )
    return coordinator
