"""Vision analysis agent for processing images and PDFs."""

from agents import RunConfig

import stf_agents.prompts as prompts
from stf_agents.base import BaseSTFAgent
from tools.stf_tools import vision_media


class VisionAgent(BaseSTFAgent):
    """
    Specialized agent for analyzing scientific figures and documents.

    Capabilities:
    - Analyze images from URLs
    - Process PDF documents
    - Extract sequence-function data from visual content
    - Support up to 8 images and 1 PDF per request
    """

    def __init__(self, run_config: RunConfig):
        """
        Initialize the Vision Analysis agent.

        Args:
            run_config: Run configuration with model settings
        """
        super().__init__(
            name="Vision Analysis Agent",
            instructions=prompts.VISION_AGENT_INSTRUCTIONS,
            run_config=run_config,
            tools=[vision_media],
            handoff_description="Analyze images and PDF documents from URLs to extract sequence-function data",
        )
