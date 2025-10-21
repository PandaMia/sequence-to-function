"""
Helper to access FastAPI app state from tools.

This allows tools to access the embedding service without using global variables.
"""
from typing import Optional
from contextvars import ContextVar

# Context variable to store current app state
_app_state_context: ContextVar = ContextVar('app_state_context', default=None)


def set_app_state_context(app_state):
    """Set the current app state in context."""
    _app_state_context.set(app_state)


def get_app_state_context():
    """Get the current app state from context."""
    return _app_state_context.get()


def get_embedding_service():
    """
    Get embedding service from app state context.

    Returns:
        EmbeddingService or None if not available
    """
    app_state = get_app_state_context()
    if app_state and hasattr(app_state, 'embedding_service'):
        return app_state.embedding_service
    return None
