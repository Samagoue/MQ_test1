"""Database connection and query execution."""

import mysql.connector
from typing import Tuple, List, Optional

class DatabaseConnection:
    """Manage MariaDB database connections."""
   
    def __init__(self, host: str, user: str, password: str, database: str, port: int = 3306):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.conn = None
   
    def connect(self) -> bool:
        """Establish database connection."""
        try:
            self.conn = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                port=self.port
            )
            print(f"✓ Connected to {self.database} on {self.host}")
            return True
        except mysql.connector.Error as e:
            print(f"✗ Database connection error: {e}")
            return False
   
    def execute_query(self, query: str) -> Tuple[Optional[List[str]], Optional[List[Tuple]]]:
        """Execute query and fetch results."""
        if not self.conn:
            return None, None
       
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            cursor.close()
            return columns, rows
        except mysql.connector.Error as e:
            print(f"✗ Query execution error: {e}")
            return None, None
   
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            print("✓ Database connection closed")
