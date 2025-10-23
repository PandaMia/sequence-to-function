"""API router for sequence-to-function endpoints."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app_startup.state import AppState
from app_startup.dependencies import get_app_state
from api.stf.schemas import StfRequest
from api.stf.runners import run_stf_agent_stream

router = APIRouter(prefix="/stf", tags=["stf"])


@router.post("/extract")
async def extract_sequence_function(
    request: StfRequest,
    session_id: str = Query(..., alias="session-id"),
    app_state: AppState = Depends(get_app_state),
):
    """
    Extract protein/gene sequence-to-function relationships from a research article.

    Args:
        request: Contains user message (article link or query) and model configuration
        session_id: Session ID for conversation tracking
        app_state: Application state with clients and services

    Returns:
        Streaming response with extraction progress and results
    """
    return StreamingResponse(
        run_stf_agent_stream(request, app_state, session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
