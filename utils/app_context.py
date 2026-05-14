"""Helper to access FastAPI app state from tools."""

from contextvars import ContextVar

# Context variable to store current app state
_app_state_context: ContextVar = ContextVar('app_state_context', default=None)
_session_id_context: ContextVar = ContextVar('session_id_context', default=None)


def set_app_state_context(app_state):
    """Set the current app state in context."""
    _app_state_context.set(app_state)


def get_app_state_context():
    """Get the current app state from context."""
    return _app_state_context.get()


def set_session_id_context(session_id: str):
    """Set the current agent session ID in context."""
    _session_id_context.set(session_id)


def get_session_id_context():
    """Get the current agent session ID from context."""
    return _session_id_context.get()
