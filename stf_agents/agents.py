"""Factory for creating the consolidated STF agent."""

from agents import Agent, RunConfig

from stf_agents.agent import STFAgent


def create_stf_agent(run_config: RunConfig) -> Agent:
    """Create the single sequence-to-function agent."""
    return STFAgent(run_config=run_config)
