"""Application state management."""

import os
import logging
from typing import Optional
from pydantic import BaseModel
from openai import AsyncOpenAI, DefaultAioHttpClient

from utils.sqlite_utils import ensure_db_folder_exists
from utils.database_utils import initialize_database
from utils.app_context import set_app_state_context
from utils.secret_manager import get_openai_api_key
from utils.usage_limits import UsageLimiter

logger = logging.getLogger(__name__)


class AppState(BaseModel):
    """FastAPI application state."""

    openai_client: AsyncOpenAI
    port: int
    usage_limiter: UsageLimiter

    class Config:
        arbitrary_types_allowed = True


class AppStateManager:
    """Manages the application state lifecycle."""

    def __init__(self) -> None:
        self._state: Optional[AppState] = None

    @property
    def state(self) -> Optional[AppState]:
        return self._state

    async def startup(self) -> AppState:
        """Initialize application state."""
        if self._state is not None:
            return self._state

        logger.info("Starting application state initialization...")

        # Ensure SQLite database folder exists for session storage
        ensure_db_folder_exists()

        openai_api_key = get_openai_api_key()

        # Create AsyncOpenAI client with aiohttp
        openai_client = AsyncOpenAI(
            api_key=openai_api_key,
            http_client=DefaultAioHttpClient(),
        )

        # Set initial app state context for tools that need shared services.
        temp_app_state = type("obj", (object,), {"openai_client": openai_client})()
        set_app_state_context(temp_app_state)

        await initialize_database()
        logger.info("Database initialized")

        # Create app state
        self._state = AppState(
            openai_client=openai_client,
            port=int(os.getenv("PORT", 8080)),
            usage_limiter=UsageLimiter(),
        )

        logger.info("Application state initialized successfully")
        return self._state

    async def shutdown(self) -> None:
        """Clean up application state."""
        if self._state is None:
            return

        logger.info("Shutting down application state...")

        # Close OpenAI client
        await self._state.openai_client.close()
        logger.info("OpenAI client closed")

        self._state = None
        logger.info("Application state shutdown complete")
