from typing import TypedDict
from agents import ModelSettings
from openai.types.shared import Reasoning
from configs.types import ModelName


class TaskModelConfig(TypedDict):
    model_name: ModelName
    model_settings: ModelSettings


DEFAULT_STF_MODEL_SETTINGS: dict[str, TaskModelConfig] = {
    "model_name": "gpt-5",
    "model_settings": ModelSettings(
        reasoning=Reasoning(effort="high", summary="auto"),
        verbosity="low",
        response_include=["reasoning.encrypted_content"],
        truncation="auto",
    ),
}

# CSV file structure configuration
CSV_HEADERS = [
    "id",
    "article_id",
    "gene",
    "protein_uniprot_id",
    "modification_type",
    "interval",
    "function",
    "effect",
    "is_longevity_related",
    "longevity_association",
    "citations",
    "created_at",
]

ARTICLE_CSV_HEADERS = [
    "id",
    "url",
    "article_text",
    "created_at",
    "updated_at",
]

CSV_FILE_PATH = "data/sequence_data.csv"
ARTICLE_CSV_FILE_PATH = "data/articles.csv"
