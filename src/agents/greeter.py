from google.adk.agents import LlmAgent


def build_greeter(cfg: dict) -> LlmAgent:
    return LlmAgent(
        model=cfg.get("model", "gemini-2.0-flash"),
        name=cfg.get("name", "greeter"),
        description=cfg.get("description", "Greets the user and clarifies intent."),
        instruction=cfg.get(
            "instruction",
            (
                "Greet the user warmly. Ask brief, targeted questions to clarify their goal. "
                "Summarize the user's intent and key constraints in 1-2 sentences."
            ),
        ),
    )
