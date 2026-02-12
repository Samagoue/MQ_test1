"""Database connection and query execution."""

import time
import mysql.connector
from typing import Tuple, List, Optional
from utils.logging_config import get_logger

logger = get_logger("core.database")

class DatabaseConnection:
    """Manage MariaDB database connections."""

    # Connection settings
    CONNECTION_TIMEOUT = 30  # seconds
    QUERY_TIMEOUT = 300  # seconds (5 minutes for large queries)
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    def __init__(self, host: str, user: str, password: str, database: str, port: int = 3306):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.conn = None

    def connect(self, retries: int = None) -> bool:
        """Establish database connection with retry logic."""
        if retries is None:
            retries = self.MAX_RETRIES

        for attempt in range(retries):
            try:
                self.conn = mysql.connector.connect(
                    host=self.host,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    port=self.port,
                    connection_timeout=self.CONNECTION_TIMEOUT
                )
                logger.info(f"✓ Connected to {self.database} on {self.host}")
                return True
            except mysql.connector.Error as e:
                if attempt < retries - 1:
                    logger.warning(f"Connection attempt {attempt + 1} failed: {e}. Retrying in {self.RETRY_DELAY}s...")
                    time.sleep(self.RETRY_DELAY)
                else:
                    logger.error(f"Database connection error after {retries} attempts: {e}")
                    return False
        return False

    def execute_query(self, query: str) -> Tuple[Optional[List[str]], Optional[List[Tuple]]]:
        """Execute query and fetch results with proper resource cleanup."""
        if not self.conn:
            return None, None

        cursor = None
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return columns, rows
        except mysql.connector.Error as e:
            logger.error(f"Query execution error: {e}")
            return None, None
        finally:
            # Always close cursor to prevent resource leak
            if cursor is not None:
                try:
                    cursor.close()
                except Exception as e:
                    logger.debug(f"Cursor cleanup error (non-critical): {e}")

    def close(self):
        """Close database connection."""
        if self.conn:
            try:
                self.conn.close()
                logger.info("✓ Database connection closed")
            except Exception as e:
                logger.warning(f"Warning during connection close: {e}")
            finally:
                self.conn = None
