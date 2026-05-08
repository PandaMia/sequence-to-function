"""Base agent class for the STF agent."""

from typing import Optional

from agents import Agent, RunConfig


class BaseSTFAgent(Agent):
    """Common initialization for the STF agent."""

    def __init__(
        self,
        name: str,
        instructions: str,
        run_config: RunConfig,
        tools: list = None,
        output_type: Optional[type] = None,
    ):
        """
        Initialize a base STF agent.

        Args:
            name: Agent name
            instructions: Agent instructions/prompt
            run_config: Run configuration with model settings
            tools: List of tools available to the agent
            output_type: Expected output type/schema
        """
        agent_kwargs = {
            "name": name,
            "instructions": instructions,
            "tools": tools or [],
            "model": run_config.model,
            "reset_tool_choice": True,
        }

        if output_type:
            agent_kwargs["output_type"] = output_type

        if run_config.model_settings is not None:
            agent_kwargs["model_settings"] = run_config.model_settings

        super().__init__(**agent_kwargs)
