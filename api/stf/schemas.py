"""API request and response schemas for STF endpoints."""

from pydantic import BaseModel, Field

# Import StfRequest from configs (reuse existing schema)
from configs.endpoints_base_models import StfRequest

# Re-export for convenience
__all__ = ["StfRequest", "StfResponse"]


class StfResponse(BaseModel):
    """Response model for sequence-to-function extraction."""

    session_id: str = Field(..., description="Session ID for tracking the conversation")
    status: str = Field(..., description="Status of the extraction process")
