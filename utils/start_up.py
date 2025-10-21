import os
import logging
from typing import AsyncIterator

from fastapi import FastAPI
from contextlib import asynccontextmanager
from openai import AsyncOpenAI, DefaultAioHttpClient

from configs.endpoints_base_models import AppState
from utils.sqlite_utils import ensure_db_folder_exists
from utils.postgres_utils import initialize_postgres
from utils.embeddings import EmbeddingService
from utils.app_context import set_app_state_context


# Configure logging
def configure_logging():
    """Configure logging for the application"""
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

logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan_start_up(app: FastAPI) -> AsyncIterator[None]:
    # Configure logging first
    configure_logging()
    logger.info("Starting the app...")

    # SQLite operations: Ensure database folder exists for session storage
    ensure_db_folder_exists()

    # Initialize the app state
    openai_api_key = os.environ["OPENAI_API_KEY"]

    # Create AsyncOpenAI client with aiohttp
    openai_client = AsyncOpenAI(
        api_key=openai_api_key,
        http_client=DefaultAioHttpClient(),
    )

    # Initialize embedding service BEFORE loading CSV data
    embedding_service = EmbeddingService(openai_client)
    logger.info("Embedding service initialized")

    # Set initial app state context for CSV import
    temp_app_state = type('obj', (object,), {'embedding_service': embedding_service})()
    set_app_state_context(temp_app_state)

    # Initialize Postgres database
    await initialize_postgres()

    app_state = AppState(
        openai_client=openai_client,
        embedding_service=embedding_service,
        port=int(os.getenv("PORT", 8080)),
    )

    logger.info("App started")

    # Set the app state
    app.state = app_state

    try:
        yield
    finally:
        logger.info("Shutting down the app...")
        await openai_client.close()