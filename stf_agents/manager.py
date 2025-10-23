"""Manager agent for coordinating STF operations."""

from agents import Agent, RunConfig

import stf_agents.prompts as prompts
from stf_agents.base import BaseSTFAgent


class STFManagerAgent(BaseSTFAgent):
    """
    Manager agent that coordinates sequence-to-function extraction tasks.

    Routes requests to specialized agents for:
    - Article parsing
    - Data retrieval
    - Article writing
    - Vision analysis
    """

    def __init__(
        self,
        run_config: RunConfig,
        article_parsing_agent: Agent,
        data_retrieval_agent: Agent,
        article_writing_agent: Agent,
        vision_agent: Agent,
    ):
        """
        Initialize the STF Manager agent with handoff agents.

        Args:
            run_config: Run configuration with model settings
            article_parsing_agent: Agent for parsing research articles
            data_retrieval_agent: Agent for querying database
            article_writing_agent: Agent for writing content
            vision_agent: Agent for analyzing images and PDFs
        """
        super().__init__(
            name="Sequence To Function Manager",
            instructions=prompts.MANAGER_INSTRUCTIONS,
            run_config=run_config,
            tools=[],
            handoffs=[
                article_parsing_agent,
                data_retrieval_agent,
                article_writing_agent,
                vision_agent,
            ],
        )
