"""PostgreSQL database utilities for sequence data storage."""

import logging
from configs.database import create_tables
from utils.database_service import DatabaseService

logger = logging.getLogger(__name__)


async def initialize_postgres():
    """Initialize PostgreSQL database tables and load CSV data."""
    # PostgreSQL operations: Initialize database tables
    await create_tables()
    logger.info("PostgreSQL tables created/verified")
    
    # PostgreSQL operations: Initialize CSV and load data into database on startup
    await DatabaseService.initialize_csv_data()