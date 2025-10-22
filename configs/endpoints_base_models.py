from pydantic import BaseModel, Field
from typing import Optional, Any
from openai import AsyncOpenAI
from agents import ModelSettings
from configs.config import DEFAULT_STF_MODEL_SETTINGS
from configs.types import ModelName


class AppState(BaseModel):
    openai_client: AsyncOpenAI
    embedding_service: Optional[Any] = None  # EmbeddingService, but using Any to avoid circular import
    port: int

    class Config:
        arbitrary_types_allowed = True


class ModelConfig(BaseModel):
    """Configuration for a model including name and settings."""

    model_name: ModelName
    model_settings: ModelSettings = Field(
        description="Model settings (reasoning effort, verbosity, etc.)"
    )


class StfRequest(BaseModel):
    user_message: str
    session_id: Optional[str] = None
    stf_model: ModelConfig = Field(
        default_factory=lambda: ModelConfig(
            model_name=DEFAULT_STF_MODEL_SETTINGS["model_name"],
            model_settings=DEFAULT_STF_MODEL_SETTINGS["model_settings"]
        ),
        description="Master model configuration (accepts string or ModelConfig object)"
    )


class SQLQueryRequest(BaseModel):
    """Request model for executing SQL queries in testing endpoints"""
    query: str = Field(description="SQL query to execute")