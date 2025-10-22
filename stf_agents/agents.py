from agents import Agent
from agents import RunConfig
import stf_agents.prompts as prompts
from stf_agents.tools import (
    save_to_database,
    fetch_article_content,
    execute_sql_query,
    get_uniprot_id,
    vision_media,
    semantic_search,
)
from stf_agents.schemas import ParsingOutput


def create_stf_manager_agent(
    run_config: RunConfig,
    article_parsing_agent: Agent,
    data_retrieval_agent: Agent,
    article_writing_agent: Agent,
    vision_agent: Agent
) -> Agent:
    agent_kwargs = {
        "name": "Sequence To Function Manager",
        "instructions": prompts.MANAGER_INSTRUCTIONS,
        "tools": [],
        "handoffs": [
            article_parsing_agent,
            data_retrieval_agent,
            article_writing_agent,
            vision_agent,
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
        "handoff_description": "Analyze research articles to extract longevity-related genes and sequence-function relationships.",
        "model": run_config.model,
        "reset_tool_choice": True,
        "output_type": ParsingOutput
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
            semantic_search,
        ],
        "handoff_description": "Query the sequence-function database using SQL and semantic search. Find genes, proteins, and research data based on user requests.",
        "model": run_config.model,
        "reset_tool_choice": True,
    }

    if run_config.model_settings is not None:
        agent_kwargs["model_settings"] = run_config.model_settings

    return Agent(**agent_kwargs)


def create_article_writing_agent(
    run_config: RunConfig,
) -> Agent:
    agent_kwargs = {
        "name": "Article Writing Agent",
        "instructions": prompts.ARTICLE_WRITING_INSTRUCTIONS,
        "tools": [
            semantic_search
        ],
        "handoff_description": "Generate research articles, summaries, and reports based on sequence-function data stored in the database. Create scientific content about longevity genes and pathways.",
        "model": run_config.model,
        "reset_tool_choice": True,
    }

    if run_config.model_settings is not None:
        agent_kwargs["model_settings"] = run_config.model_settings

    return Agent(**agent_kwargs)


def create_vision_agent(run_config: RunConfig) -> Agent:
    """
    Create a Vision Analysis Agent that processes image and PDF URLs.

    This agent specializes in analyzing scientific figures and documents to extract
    sequence-function information. It can process up to 8 images and 1 PDF per request.

    Args:
        run_config: Run configuration with model settings

    Returns:
        Configured Vision Agent
    """
    agent_kwargs = {
        "name": "Vision Analysis Agent",
        "instructions": prompts.VISION_AGENT_INSTRUCTIONS,
        "tools": [vision_media],
        "handoff_description": "Analyze images and PDF documents from URLs to extract sequence-function data",
        "model": run_config.model,
        "reset_tool_choice": True,
    }

    if run_config.model_settings is not None:
        agent_kwargs["model_settings"] = run_config.model_settings

    return Agent(**agent_kwargs)