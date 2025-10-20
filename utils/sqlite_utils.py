"""SQLite database utilities for session storage and chat history."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# SQLite database folder configuration
SQLITE_DB_FOLDER = "databases"
SQLITE_DB_PATH = Path(SQLITE_DB_FOLDER)


def ensure_db_folder_exists():
    """Ensure the SQLite database folder exists."""
    SQLITE_DB_PATH.mkdir(exist_ok=True)
    logger.info(f"SQLite database folder ensured at: {SQLITE_DB_PATH.absolute()}")


def get_db_path(db_name: str) -> str:
    """Get the full path for a SQLite database file."""
    return str(SQLITE_DB_PATH / db_name)