"""FastAPI lifespan management."""

import logging
from typing import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app_startup.state import AppStateManager

logger = logging.getLogger(__name__)


# Configure logging
def configure_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )
    # Set uvicorn logger to use the same configuration
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)


# Global state manager
state_manager = AppStateManager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage FastAPI application lifespan."""
    # Configure logging first
    configure_logging()
    logger.info("Starting the application...")

    # Initialize app state
    app_state = await state_manager.startup()

    # Set the app state
    app.state = app_state

    try:
        yield
    finally:
        # Shutdown app state
        await state_manager.shutdown()
        logger.info("Application shutdown complete")
