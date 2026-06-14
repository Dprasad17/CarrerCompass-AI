import sqlite3
import logging
from contextlib import contextmanager
from typing import Generator
from src.core.config import settings

logger = logging.getLogger("DatabaseConnection")

class DatabaseConnectionManager:
    """
    Context manager for managing SQLite database connections safely.
    Handles foreign key enforcement, WAL mode execution, and connection cleanup.
    """
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        import os
        if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
            logger.info("Database file not found or empty. Auto-initializing schema...")
            try:
                from database.init_db import init_database
                init_database()
            except Exception as e:
                logger.error(f"Failed to auto-initialize database schema: {e}")

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = None
        try:

            # Connect to the SQLite database file
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()

            # Enforce foreign key constraints and WAL journal mode
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.execute("PRAGMA journal_mode = WAL;")
            cursor.close()

            yield conn
        except sqlite3.Error as e:
            logger.error(f"Failed to establish database connection or set PRAGMAs: {e}")
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()

# Global database connection pool/helper instance
db_manager = DatabaseConnectionManager(str(settings.db_path))
