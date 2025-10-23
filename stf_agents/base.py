"""Base agent class for STF agents."""

from agents import Agent, RunConfig
from typing import Optional


class BaseSTFAgent(Agent):
    """
    Base class for all STF agents.

    Provides common initialization and configuration for specialized agents.
    """

    def __init__(
        self,
        name: str,
        instructions: str,
        run_config: RunConfig,
        tools: list = None,
        handoffs: list = None,
        handoff_description: Optional[str] = None,
        output_type: Optional[type] = None,
    ):
        """
        Initialize a base STF agent.

        Args:
            name: Agent name
            instructions: Agent instructions/prompt
            run_config: Run configuration with model settings
            tools: List of tools available to the agent
            handoffs: List of agents this agent can handoff to
            handoff_description: Description for handoff capability
            output_type: Expected output type/schema
        """
        agent_kwargs = {
            "name": name,
            "instructions": instructions,
            "tools": tools or [],
            "handoffs": handoffs or [],
            "model": run_config.model,
            "reset_tool_choice": True,
        }

        if handoff_description:
            agent_kwargs["handoff_description"] = handoff_description

        if output_type:
            agent_kwargs["output_type"] = output_type

        if run_config.model_settings is not None:
            agent_kwargs["model_settings"] = run_config.model_settings

        super().__init__(**agent_kwargs)
