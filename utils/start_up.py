import os
import logging
from typing import AsyncIterator

from fastapi import FastAPI
from contextlib import asynccontextmanager
from openai import AsyncOpenAI, DefaultAioHttpClient

from configs.endpoints_base_models import AppState
from configs.database import create_tables

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan_start_up(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting the app...")

    # Initialize database tables
    await create_tables()
    logger.info("Database tables created/verified")

    # Initialize the app state
    openai_api_key = os.environ["OPENAI_API_KEY"]

    # Create AsyncOpenAI client with aiohttp
    openai_client = AsyncOpenAI(
        api_key=openai_api_key,
        http_client=DefaultAioHttpClient(),
    )

    app_state = AppState(
        openai_client=openai_client,
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