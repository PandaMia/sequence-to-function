from agents import Agent
from agents import RunConfig
from stf_agents.prompts import INSTRUCTIONS
from stf_agents.tools import (
    save_to_database,
    fetch_article_content,
)


def create_stf_agent(run_config: RunConfig) -> Agent:
    agent_kwargs = {
        "name": "Sequence-to-fuction Agent",
        "instructions": INSTRUCTIONS,
        "tools": [
            save_to_database,
            fetch_article_content,
        ],
        "model": run_config.model,
        "reset_tool_choice": True,
    }

    # Only add model_settings if it's not None
    if run_config.model_settings is not None:
        agent_kwargs["model_settings"] = run_config.model_settings

    return Agent(**agent_kwargs)