
import json
from typing import List
import os
import base64
from typing import Optional
import requests
from openai import OpenAI
from dotenv import load_dotenv
import logging
from stf_agents.schemas import FigureFinding


logger = logging.getLogger(__name__)

load_dotenv()

def _download_b64(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return "data:image/*;base64," + base64.b64encode(resp.content).decode("utf-8")


def vision_agent_process_images(image_urls: list[str], hint: Optional[str] = None) -> List[FigureFinding]:
    sys_prompt = """
        You are a scientific figure analyst.
        Extract proteins/genes, modifications (with positions if visible),
        and concise claims; include a short OCR-like summary.
        """
    user_prompt = "Analyze these figures for sequence-function evidence."
    if hint:
        user_prompt += f" Context hint: {hint}"

    parts = [{"type": "input_text", "text": user_prompt}]
    for url in image_urls:
        try:
            parts.append({"type":"input_image","image_url": _download_b64(url)})
        except Exception as e:
            logger.error("Failed to download image from URL: %s, error: %s", url, str(e))
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.responses.create(
        model="gpt-5-mini",
        input=[
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": parts},
        ],
        temperature=0,
        max_output_tokens=400,
        text={
            "format": {
                "type": "json_schema",
                "name": "VisionFindings",
                "schema": {"type": "array", "items": FigureFinding.model_json_schema()},
                "strict": True,
            }
        },
    )

    raw = json.loads(resp.output_text or "[]")

    return [FigureFinding.model_validate(item) for item in raw]