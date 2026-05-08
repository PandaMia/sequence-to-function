"""Single STF agent with all sequence-to-function tools."""

from agents import RunConfig

import stf_agents.prompts as prompts
from stf_agents.base import BaseSTFAgent
from tools.stf_tools import (
    execute_sql_query,
    fetch_article_content,
    get_uniprot_id,
    save_to_database,
    semantic_search,
    vision_media,
    web_search,
)


class STFAgent(BaseSTFAgent):
    """Consolidated sequence-to-function agent."""

    def __init__(self, run_config: RunConfig):
        super().__init__(
            name="STF Agent",
            instructions=prompts.STF_AGENT_INSTRUCTIONS,
            run_config=run_config,
            tools=[
                fetch_article_content,
                web_search,
                get_uniprot_id,
                save_to_database,
                execute_sql_query,
                semantic_search,
                vision_media,
            ],
        )
