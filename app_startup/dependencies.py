"""FastAPI dependencies."""

from fastapi import Request
from app_startup.state import AppState


def get_app_state(request: Request) -> AppState:
    """Get application state from FastAPI request."""
    return request.app.state
