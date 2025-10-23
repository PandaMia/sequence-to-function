"""Application state management."""

import os
import logging
from typing import Optional
from pydantic import BaseModel
from openai import AsyncOpenAI, DefaultAioHttpClient

from utils.embeddings import EmbeddingService
from utils.sqlite_utils import ensure_db_folder_exists
from utils.postgres_utils import initialize_postgres
from utils.app_context import set_app_state_context

logger = logging.getLogger(__name__)


class AppState(BaseModel):
    """FastAPI application state."""

    openai_client: AsyncOpenAI
    embedding_service: EmbeddingService
    port: int

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

        # Get OpenAI API key
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        # Create AsyncOpenAI client with aiohttp
        openai_client = AsyncOpenAI(
            api_key=openai_api_key,
            http_client=DefaultAioHttpClient(),
        )

        # Initialize embedding service
        embedding_service = EmbeddingService(openai_client)
        logger.info("Embedding service initialized")

        # Set initial app state context for database operations
        temp_app_state = type('obj', (object,), {'embedding_service': embedding_service})()
        set_app_state_context(temp_app_state)

        # Initialize Postgres database
        await initialize_postgres()
        logger.info("PostgreSQL database initialized")

        # Create app state
        self._state = AppState(
            openai_client=openai_client,
            embedding_service=embedding_service,
            port=int(os.getenv("PORT", 8080)),
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
