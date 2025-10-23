"""Article writing agent for generating scientific content."""

from agents import RunConfig

import stf_agents.prompts as prompts
from stf_agents.base import BaseSTFAgent
from tools.stf_tools import semantic_search


class ArticleWritingAgent(BaseSTFAgent):
    """
    Specialized agent for generating research articles and summaries.

    Capabilities:
    - Create research articles based on database data
    - Generate review articles
    - Write summaries and reports
    - Perform comparative analysis
    """

    def __init__(self, run_config: RunConfig):
        """
        Initialize the Article Writing agent.

        Args:
            run_config: Run configuration with model settings
        """
        super().__init__(
            name="Article Writing Agent",
            instructions=prompts.ARTICLE_WRITING_INSTRUCTIONS,
            run_config=run_config,
            tools=[semantic_search],
            handoff_description="Generate research articles, summaries, and reports based on sequence-function data stored in the database. Create scientific content about longevity genes and pathways.",
        )
