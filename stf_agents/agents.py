"""Agent factory functions for creating STF agents.

This module provides factory functions for creating agents,
maintaining backward compatibility with the existing codebase.
"""

from agents import Agent, RunConfig

from stf_agents.manager import STFManagerAgent
from stf_agents.article_parsing import ArticleParsingAgent
from stf_agents.data_retrieval import DataRetrievalAgent
from stf_agents.article_writing import ArticleWritingAgent
from stf_agents.vision import VisionAgent


def create_stf_manager_agent(
    run_config: RunConfig,
    article_parsing_agent: Agent,
    data_retrieval_agent: Agent,
    article_writing_agent: Agent,
    vision_agent: Agent
) -> Agent:
    """
    Create the STF Manager agent.

    Args:
        run_config: Run configuration with model settings
        article_parsing_agent: Agent for parsing research articles
        data_retrieval_agent: Agent for querying database
        article_writing_agent: Agent for writing content
        vision_agent: Agent for analyzing images and PDFs

    Returns:
        Configured STF Manager agent
    """
    return STFManagerAgent(
        run_config=run_config,
        article_parsing_agent=article_parsing_agent,
        data_retrieval_agent=data_retrieval_agent,
        article_writing_agent=article_writing_agent,
        vision_agent=vision_agent,
    )


def create_article_parsing_agent(run_config: RunConfig) -> Agent:
    """
    Create the Article Parsing agent.

    Args:
        run_config: Run configuration with model settings

    Returns:
        Configured Article Parsing agent
    """
    return ArticleParsingAgent(run_config=run_config)


def create_data_retrieval_agent(run_config: RunConfig) -> Agent:
    """
    Create the Data Retrieval agent.

    Args:
        run_config: Run configuration with model settings

    Returns:
        Configured Data Retrieval agent
    """
    return DataRetrievalAgent(run_config=run_config)


def create_article_writing_agent(run_config: RunConfig) -> Agent:
    """
    Create the Article Writing agent.

    Args:
        run_config: Run configuration with model settings

    Returns:
        Configured Article Writing agent
    """
    return ArticleWritingAgent(run_config=run_config)


def create_vision_agent(run_config: RunConfig) -> Agent:
    """
    Create the Vision Analysis agent.

    Args:
        run_config: Run configuration with model settings

    Returns:
        Configured Vision agent
    """
    return VisionAgent(run_config=run_config)
