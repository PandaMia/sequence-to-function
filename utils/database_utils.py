"""Database initialization utilities."""

import logging

from configs.database import create_tables
from utils.database_service import DatabaseService

logger = logging.getLogger(__name__)


async def initialize_database() -> None:
    """Initialize database tables and seed CSV data when the database is empty."""

    await create_tables()
    logger.info("Database tables created/verified")

    await DatabaseService.initialize_csv_data()
    logger.info("Database CSV initialization completed")
