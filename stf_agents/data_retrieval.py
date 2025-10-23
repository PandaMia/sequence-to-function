"""Data retrieval agent for querying the sequence-function database."""

from agents import RunConfig

import stf_agents.prompts as prompts
from stf_agents.base import BaseSTFAgent
from tools.stf_tools import execute_sql_query, semantic_search


class DataRetrievalAgent(BaseSTFAgent):
    """
    Specialized agent for querying and retrieving data from the database.

    Capabilities:
    - Execute SQL queries
    - Perform semantic search using embeddings
    - Find genes, proteins, and research data
    """

    def __init__(self, run_config: RunConfig):
        """
        Initialize the Data Retrieval agent.

        Args:
            run_config: Run configuration with model settings
        """
        super().__init__(
            name="Data Retrieval Agent",
            instructions=prompts.DATA_RETRIEVAL_INSTRUCTIONS,
            run_config=run_config,
            tools=[
                execute_sql_query,
                semantic_search,
            ],
            handoff_description="Query the sequence-function database using SQL and semantic search. Find genes, proteins, and research data based on user requests.",
        )
