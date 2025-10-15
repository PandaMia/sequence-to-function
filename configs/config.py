from typing import TypedDict
from agents import ModelSettings
from openai.types.shared import Reasoning
from configs.types import ModelName


class TaskModelConfig(TypedDict):
    model_name: ModelName
    model_settings: ModelSettings


DEFAULT_STF_MODEL_SETTINGS: dict[str, TaskModelConfig] = {
    "model_name": "gpt-5-nano",
    "model_settings": ModelSettings(
        reasoning=Reasoning(effort="low", summary="auto"),
        verbosity="low",
        response_include=["reasoning.encrypted_content"],
        truncation="auto",
    ),
}