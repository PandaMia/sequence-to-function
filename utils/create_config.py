from typing import List
from openai import AsyncOpenAI
from agents.items import TResponseInputItem
from agents.models.openai_responses import OpenAIResponsesModel
from agents import RunConfig
from configs.config import TaskModelConfig, DEFAULT_STF_MODEL_SETTINGS


def create_stf_run_config(
    openai_client: AsyncOpenAI,
    session_id: str,
    stf_model_config: TaskModelConfig | None = None,
) -> RunConfig:
    
    # Use defaults if not provided
    stf_model_config = stf_model_config or DEFAULT_STF_MODEL_SETTINGS

    # Create STF model
    stf_model = OpenAIResponsesModel(stf_model_config["model_name"], openai_client=openai_client)

    # Build metadata for STF agent
    stf_metadata = {
        "session_id": session_id,
        "trace_name": "stf-extraction",
        "generation_name": "stf-extraction",
        "tags": ["sequence-to-function"],
    }

    stf_run_config = RunConfig(
        model=stf_model,
        model_settings=stf_model_config["model_settings"],
        session_input_callback=merge_history,
        trace_metadata=stf_metadata,
        tracing_disabled=True,
    )

    return stf_run_config


def merge_history(
    history: List[TResponseInputItem],
    new_input: List[TResponseInputItem],
) -> List[TResponseInputItem]:
    return history + new_input