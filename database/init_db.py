import sqlite3
import logging
from pathlib import Path
import sys

# Ensure parent path is in python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.config import settings

logger = logging.getLogger("DatabaseInitializer")

def init_database() -> None:
    """
    Reads schema.sql and creates all tables, foreign keys, and indexes in SQLite.
    Also activates WAL mode for improved concurrent writing performances.
    """
    db_path = settings.db_path
    schema_file = Path(__file__).resolve().parent.parent / "data" / "schema.sql"

    if not schema_file.exists():
        logger.error(f"Initialization failed: schema.sql file not found at {schema_file}")
        raise FileNotFoundError(f"Could not locate schema.sql at {schema_file}")

    logger.info(f"Initializing SQLite database at: {db_path}")

    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Enable WAL mode and Foreign Keys
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")

        # Read and execute SQL schema
        with open(schema_file, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        cursor.executescript(schema_sql)
        conn.commit()

        # Check WAL mode activation status
        cursor.execute("PRAGMA journal_mode;")
        current_mode = cursor.fetchone()[0]

        logger.info(f"Database successfully initialized. Journal mode configured to: {current_mode.upper()}")

    except sqlite3.Error as e:
        logger.error(f"SQLite transaction error occurred during schema execution: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    init_database()
