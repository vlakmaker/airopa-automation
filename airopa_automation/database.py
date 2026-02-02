"""
Database Module - Database connectivity and operations

This module provides a unified interface for database operations
across different database backends (SQLite, PostgreSQL, etc.).
"""

"""
Database Module - Database connectivity and operations

This module provides a unified interface for database operations
across different database backends (SQLite, PostgreSQL, etc.).
"""

import os
import sqlite3
from typing import Any, Optional


class Database:
    """
    Database connection and operations manager.

    Provides a unified interface for database operations with support
    for multiple database backends.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize database connection.

        Args:
            config (dict[str, Any]): Database configuration
        """
        self.config = config
        self.connection = None
        self.cursor = None

    def connect(self) -> bool:
        """
        Establish database connection.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            db_type = self.config.get("type", "sqlite")

            if db_type == "sqlite":
                db_path = self.config.get("path", "database/airopa.db")
                # Ensure directory exists
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                self.connection = sqlite3.connect(db_path)
                self.cursor = self.connection.cursor()
                return True

            raise ValueError(f"Unsupported database type: {db_type}")

        except Exception as e:
            print(f"Error connecting to database: {e}")
            return False

    def disconnect(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.cursor = None

    def execute(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> bool:
        """
        Execute a SQL query.

        Args:
            query (str): SQL query to execute
            params (tuple[Any, ...] | None): Parameters for the query

        Returns:
            bool: True if execution successful, False otherwise
        """
        try:
            if not self.connection:
                if not self.connect():
                    return False

            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)

            return True

        except Exception as e:
            print(f"Error executing query: {e}")
            return False

    def fetch_one(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> Optional[tuple[Any, ...]]:
        """
        Execute query and fetch one result.

        Args:
            query (str): SQL query to execute
            params (tuple[Any, ...] | None): Parameters for the query

        Returns:
            Optional[tuple[Any, ...]]: First result row or None
        """
        if self.execute(query, params):
            return self.cursor.fetchone()
        return None

    def fetch_all(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[tuple[Any, ...]]:
        """
        Execute query and fetch all results.

        Args:
            query (str): SQL query to execute
            params (tuple[Any, ...] | None): Parameters for the query

        Returns:
            list[tuple[Any, ...]]: All result rows
        """
        if self.execute(query, params):
            return self.cursor.fetchall()
        return []

    def commit(self) -> None:
        """Commit pending transactions."""
        if self.connection:
            self.connection.commit()

    def rollback(self) -> None:
        """Rollback pending transactions."""
        if self.connection:
            self.connection.rollback()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.disconnect()
