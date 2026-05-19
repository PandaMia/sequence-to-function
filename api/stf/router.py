"""API router for sequence-to-function endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app_startup.state import AppState
from app_startup.dependencies import get_app_state
from configs.endpoints_base_models import StfRequest
from api.stf.runners import run_stf_agent_stream
from utils.usage_limits import UsageLimitExceeded

router = APIRouter(prefix="/stf", tags=["stf"])


@router.post("/extract")
async def extract_sequence_function(
    http_request: Request,
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
    client_key = _client_key(http_request)
    try:
        await app_state.usage_limiter.check_request(
            client_key=client_key,
            session_id=session_id,
            message_chars=len(request.user_message),
        )
    except UsageLimitExceeded as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return StreamingResponse(
        run_stf_agent_stream(request, app_state, session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


def _client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
