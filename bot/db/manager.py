"""Database connection manager with lifecycle management.

Handles SQLite connection pooling, WAL mode, busy timeout, and schema initialization.
Supports batch insert buffering for high-throughput message storage.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from bot.config.settings import DatabaseSettings
from bot.core.exceptions import DatabaseConnectionError

logger = logging.getLogger("WeChatBot.DB")


class DatabaseManager:
    """SQLite database connection manager.

    Features:
      - WAL mode for concurrent read/write
      - Busy timeout for lock contention
      - Thread-safe connection management
      - Automatic schema migration
      - Batch insert buffering
    """

    SCHEMA_VERSION = 2

    def __init__(self, settings: DatabaseSettings):
        self._settings = settings
        self._local = threading.local()
        self._write_lock = threading.Lock()
        self._initialized = False

        # Ensure data directory exists
        db_path = Path(settings.path)
        db_dir = db_path.parent
        if db_dir and not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)

        # Initialize schema
        self._init_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection.

        Each thread gets its own connection (SQLite thread safety model).
        Connections are cached and reused within the same thread.
        """
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._settings.path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            if self._settings.wal_mode:
                conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(f"PRAGMA busy_timeout={self._settings.busy_timeout}")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            self._local.conn = conn
        return conn

    def execute_write(self, sql: str, params: Tuple = ()) -> sqlite3.Cursor:
        """Execute a write operation with thread-safe locking.

        SQLite only allows one writer at a time. This method serializes
        write operations across threads.
        """
        with self._write_lock:
            conn = self.get_connection()
            try:
                cursor = conn.execute(sql, params)
                conn.commit()
                return cursor
            except sqlite3.Error as e:
                conn.rollback()
                raise

    def execute_read(self, sql: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Execute a read query."""
        conn = self.get_connection()
        return conn.execute(sql, params).fetchall()

    def execute_read_one(self, sql: str, params: Tuple = ()) -> Optional[sqlite3.Row]:
        """Execute a read query and return one row."""
        conn = self.get_connection()
        return conn.execute(sql, params).fetchone()

    def execute_write_batch(self, statements: List[Tuple[str, Tuple]]) -> int:
        """Execute multiple write statements in a single transaction.

        Args:
            statements: List of (sql, params) tuples.

        Returns:
            Number of statements executed.
        """
        with self._write_lock:
            conn = self.get_connection()
            try:
                count = 0
                for sql, params in statements:
                    conn.execute(sql, params)
                    count += 1
                conn.commit()
                return count
            except sqlite3.Error as e:
                conn.rollback()
                logger.error("Batch write error: %s", e)
                raise

    def close(self) -> None:
        """Close the thread-local connection."""
        conn = getattr(self._local, "conn", None)
        if conn:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None

    def _init_schema(self) -> None:
        """Initialize database schema with version tracking."""
        conn = self.get_connection()

        # Create schema_version table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at REAL NOT NULL
            )
        """)

        # Check current version
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current_version = row[0] if row and row[0] else 0

        # Apply migrations
        if current_version < 1:
            self._migrate_v1(conn)
        if current_version < 2:
            self._migrate_v2(conn)

        conn.commit()
        self._initialized = True
        logger.info("Database schema initialized (version=%d)", self.SCHEMA_VERSION)

    def _migrate_v1(self, conn: sqlite3.Connection) -> None:
        """Migration v1: Initial schema."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                msg_id TEXT NOT NULL,
                room_id TEXT NOT NULL,
                sender_wxid TEXT NOT NULL,
                sender_name TEXT DEFAULT '',
                msg_type INTEGER NOT NULL,
                content TEXT DEFAULT '',
                xml_content TEXT DEFAULT '',
                created_at REAL NOT NULL,
                UNIQUE(msg_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gm_room_time ON group_messages(room_id, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gm_sender ON group_messages(sender_wxid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gm_type ON group_messages(msg_type)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS group_member_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id TEXT NOT NULL,
                member_count INTEGER NOT NULL,
                members_hash TEXT DEFAULT '',
                created_at REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gms_room_time ON group_member_snapshots(room_id, created_at)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS group_info (
                room_id TEXT PRIMARY KEY,
                room_name TEXT DEFAULT '',
                member_count INTEGER DEFAULT 0,
                owner_wxid TEXT DEFAULT '',
                updated_at REAL NOT NULL
            )
        """)

        conn.execute("INSERT INTO schema_version VALUES (1, ?)", (time.time(),))
        logger.info("Applied migration v1")

    def _migrate_v2(self, conn: sqlite3.Connection) -> None:
        """Migration v2: Add indexes for query performance."""
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gm_room_type ON group_messages(room_id, msg_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gm_created_day ON group_messages(date(created_at, 'unixepoch'))")
        conn.execute("INSERT INTO schema_version VALUES (2, ?)", (time.time(),))
        logger.info("Applied migration v2")
