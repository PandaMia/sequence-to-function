"""Vision media analysis logic for STF tools."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import OpenAI

from tools.schemas import VisionMediaInput, VisionMediaOutput
from utils.secret_manager import get_openai_api_key
from utils.stf_tool_utils import download_image_as_data_url, download_pdf_b64


logger = logging.getLogger(__name__)


def vision_media_logic(params: VisionMediaInput) -> VisionMediaOutput:
    """Analyze scientific images and PDFs for sequence-function evidence."""

    image_urls = params.image_urls[:8]
    pdf_urls = params.pdf_urls[:1]
    if not image_urls and not pdf_urls:
        return VisionMediaOutput(notes=[])

    try:
        client = OpenAI(api_key=get_openai_api_key())
        system_prompt = """
You are a scientific figure analyst. For each provided image or PDF:
1. Classify the media type.
2. Decide if it is relevant to sequence-function analysis.
3. Extract visible proteins, genes, sequence positions, mutations, assays, and concise claims.
Return JSON that matches the requested schema.
"""
        user_prompt = "Analyze these media URLs for sequence-function evidence."
        if params.hint:
            user_prompt += f"\nContext hint: {params.hint}"
        user_prompt += "\nImage URLs: " + json.dumps(image_urls)
        user_prompt += "\nPDF URLs: " + json.dumps(pdf_urls)

        parts: list[dict[str, Any]] = [{"type": "input_text", "text": user_prompt}]
        loaded_urls: list[tuple[str, str]] = []

        for url in image_urls:
            try:
                parts.append({"type": "input_image", "image_url": download_image_as_data_url(url)})
                loaded_urls.append((url, "image"))
            except Exception as exc:
                logger.error("Failed to download image from URL %s: %s", url, exc)

        for url in pdf_urls:
            try:
                b64_data, content_type, filename = download_pdf_b64(url)
                parts.append(
                    {
                        "type": "input_file",
                        "file_data": f"data:{content_type};base64,{b64_data}",
                        "filename": filename,
                    }
                )
                loaded_urls.append((url, "pdf"))
            except Exception as exc:
                logger.error("Failed to download PDF from URL %s: %s", url, exc)

        if not loaded_urls:
            return VisionMediaOutput(notes=[])

        response = client.responses.create(
            model=os.getenv("STF_VISION_MODEL", "gpt-5.4-nano"),
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": parts},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "VisionMediaOutput",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "notes": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "url": {"type": "string"},
                                        "kind": {"type": "string", "enum": ["image", "pdf"]},
                                        "description": {"type": "string"},
                                        "relevance": {"type": "boolean"},
                                        "relevance_score": {"type": "number"},
                                    },
                                    "required": [
                                        "url",
                                        "kind",
                                        "description",
                                        "relevance",
                                        "relevance_score",
                                    ],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["notes"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                }
            },
        )
        data = json.loads(response.output_text or "{}")
        return VisionMediaOutput.model_validate(data)
    except Exception as exc:
        logger.error("vision_media failed: %s", exc, exc_info=True)
        return VisionMediaOutput(notes=[])
