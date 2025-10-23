"""Article parsing agent for extracting sequence-function data from research articles."""

from agents import RunConfig

import stf_agents.prompts as prompts
from stf_agents.base import BaseSTFAgent
from stf_agents.schemas import ParsingOutput
from tools.stf_tools import (
    fetch_article_content,
    web_search_tool,
    get_uniprot_id,
    save_to_database,
)


class ArticleParsingAgent(BaseSTFAgent):
    """
    Specialized agent for extracting sequence-function relationships from scientific articles.

    Capabilities:
    - Fetch article content from URLs
    - Extract gene and protein information
    - Look up UniProt IDs
    - Save data to database
    """

    def __init__(self, run_config: RunConfig):
        """
        Initialize the Article Parsing agent.

        Args:
            run_config: Run configuration with model settings
        """
        super().__init__(
            name="Article Parsing Agent",
            instructions=prompts.ARTICLE_PARSING_INSTRUCTIONS,
            run_config=run_config,
            tools=[
                fetch_article_content,
                web_search_tool,
                get_uniprot_id,
                save_to_database,
            ],
            handoff_description="Analyze research articles to extract longevity-related genes and sequence-function relationships.",
            output_type=ParsingOutput,
        )
