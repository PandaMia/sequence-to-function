from agents import Agent
from agents import RunConfig
import stf_agents.prompts as prompts
from stf_agents.tools import (
    save_to_database,
    fetch_article_content,
    execute_sql_query,
    get_uniprot_id,
)


def create_stf_manager_agent(
    run_config: RunConfig, 
    article_parsing_agent: Agent, 
    data_retrieval_agent: Agent,
    article_writing_agent: Agent
) -> Agent:
    agent_kwargs = {
        "name": "Sequence To Function Manager",
        "instructions": prompts.MANAGER_INSTRUCTIONS,
        "tools": [],
        "handoffs": [
            article_parsing_agent,
            data_retrieval_agent,
            article_writing_agent,
        ],
        "model": run_config.model,
        "reset_tool_choice": True,
    }

    if run_config.model_settings is not None:
        agent_kwargs["model_settings"] = run_config.model_settings

    return Agent(**agent_kwargs)


def create_article_parsing_agent(run_config: RunConfig) -> Agent:
    agent_kwargs = {
        "name": "Article Parsing Agent",
        "instructions": prompts.ARTICLE_PARSING_INSTRUCTIONS,
        "tools": [
            fetch_article_content,
            get_uniprot_id,
            save_to_database,
        ],
        "handoff_description": "",
        "model": run_config.model,
        "reset_tool_choice": True,
    }

    if run_config.model_settings is not None:
        agent_kwargs["model_settings"] = run_config.model_settings

    return Agent(**agent_kwargs)


def create_data_retrieval_agent(run_config: RunConfig) -> Agent:
    agent_kwargs = {
        "name": "Data Retrieval Agent",
        "instructions": prompts.DATA_RETRIEVAL_INSTRUCTIONS,
        "tools": [
            execute_sql_query,
        ],
        "handoff_description": "",
        "model": run_config.model,
        "reset_tool_choice": True,
    }

    if run_config.model_settings is not None:
        agent_kwargs["model_settings"] = run_config.model_settings

    return Agent(**agent_kwargs)


def create_article_writing_agent(
    run_config: RunConfig,
    data_retrieval_agent: Agent,
) -> Agent:
    agent_kwargs = {
        "name": "Article Writing Agent",
        "instructions": prompts.ARTICLE_WRITING_INSTRUCTIONS,
        "tools": [],
        "handoffs": [data_retrieval_agent],
        "handoff_description": "",
        "model": run_config.model,
        "reset_tool_choice": True,
    }

    if run_config.model_settings is not None:
        agent_kwargs["model_settings"] = run_config.model_settings

    return Agent(**agent_kwargs)