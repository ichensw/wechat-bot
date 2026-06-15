"""Data access repository - clean separation of DB operations from business logic.

The Repository pattern encapsulates all database queries. Business logic
calls repository methods without knowing SQL details.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from bot.db.manager import DatabaseManager
from bot.wcf.models import MessageType

logger = logging.getLogger("WeChatBot.Repository")


class Repository:
    """Data access layer for WeChat Bot.

    All database operations go through this class.
    Provides typed query methods with no raw SQL exposure to callers.
    """

    def __init__(self, db_manager: DatabaseManager):
        self._db = db_manager

    # ── Message Operations ────────────────────────────────────────────

    def save_message(
        self,
        msg_id: str,
        room_id: str,
        sender_wxid: str,
        sender_name: str,
        msg_type: int,
        content: str,
        xml_content: str = "",
    ) -> bool:
        """Save a group message to database."""
        try:
            self._db.execute_write(
                """
                INSERT OR IGNORE INTO group_messages
                    (msg_id, room_id, sender_wxid, sender_name, msg_type, content, xml_content, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (msg_id, room_id, sender_wxid, sender_name, msg_type, content, xml_content, time.time()),
            )
            return True
        except Exception as e:
            logger.error("Failed to save message %s: %s", msg_id, e)
            return False

    def save_messages_batch(self, messages: List[Dict[str, Any]]) -> int:
        """Save multiple messages in a single transaction.

        Args:
            messages: List of message dicts with keys matching save_message params.

        Returns:
            Number of messages saved.
        """
        statements = []
        for m in messages:
            sql = """
                INSERT OR IGNORE INTO group_messages
                    (msg_id, room_id, sender_wxid, sender_name, msg_type, content, xml_content, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                m["msg_id"], m["room_id"], m["sender_wxid"],
                m.get("sender_name", ""), m["msg_type"], m.get("content", ""),
                m.get("xml_content", ""), m.get("created_at", time.time()),
            )
            statements.append((sql, params))

        try:
            return self._db.execute_write_batch(statements)
        except Exception as e:
            logger.error("Batch save failed: %s", e)
            return 0

    def get_messages(
        self,
        room_id: Optional[str] = None,
        sender_wxid: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        msg_type: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """Query messages with flexible filters."""
        conditions = []
        params: list = []

        if room_id:
            conditions.append("room_id = ?")
            params.append(room_id)
        if sender_wxid:
            conditions.append("sender_wxid = ?")
            params.append(sender_wxid)
        if start_time:
            conditions.append("created_at >= ?")
            params.append(start_time)
        if end_time:
            conditions.append("created_at <= ?")
            params.append(end_time)
        if msg_type is not None:
            conditions.append("msg_type = ?")
            params.append(msg_type)

        where = " AND ".join(conditions) if conditions else "1=1"
        query = f"""
            SELECT msg_id, room_id, sender_wxid, sender_name, msg_type, content, xml_content, created_at
            FROM group_messages
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        rows = self._db.execute_read(query, tuple(params))
        return [dict(row) for row in rows]

    def get_message_count(self, room_id: Optional[str] = None, since: Optional[float] = None) -> int:
        """Get message count."""
        conditions = []
        params: list = []

        if room_id:
            conditions.append("room_id = ?")
            params.append(room_id)
        if since:
            conditions.append("created_at >= ?")
            params.append(since)

        where = " AND ".join(conditions) if conditions else "1=1"
        result = self._db.execute_read_one(f"SELECT COUNT(*) as cnt FROM group_messages WHERE {where}", tuple(params))
        return result["cnt"] if result else 0

    # ── Member Snapshot Operations ────────────────────────────────────

    def save_member_snapshot(self, room_id: str, member_count: int, members_hash: str = "") -> bool:
        """Save a group member count snapshot."""
        try:
            self._db.execute_write(
                "INSERT INTO group_member_snapshots (room_id, member_count, members_hash, created_at) VALUES (?, ?, ?, ?)",
                (room_id, member_count, members_hash, time.time()),
            )
            return True
        except Exception as e:
            logger.error("Failed to save member snapshot for %s: %s", room_id, e)
            return False

    def get_latest_member_count(self, room_id: str) -> Optional[int]:
        """Get the latest member count for a group."""
        row = self._db.execute_read_one(
            "SELECT member_count FROM group_member_snapshots WHERE room_id = ? ORDER BY created_at DESC LIMIT 1",
            (room_id,),
        )
        return row["member_count"] if row else None

    def get_member_count_history(self, room_id: str, limit: int = 50) -> List[Dict]:
        """Get member count history."""
        rows = self._db.execute_read(
            "SELECT member_count, created_at FROM group_member_snapshots WHERE room_id = ? ORDER BY created_at DESC LIMIT ?",
            (room_id, limit),
        )
        return [dict(row) for row in rows]

    # ── Group Info Operations ─────────────────────────────────────────

    def upsert_group_info(self, room_id: str, room_name: str = "", member_count: int = 0, owner_wxid: str = "") -> bool:
        """Insert or update group info."""
        try:
            self._db.execute_write(
                """
                INSERT INTO group_info (room_id, room_name, member_count, owner_wxid, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(room_id) DO UPDATE SET
                    room_name = excluded.room_name,
                    member_count = excluded.member_count,
                    owner_wxid = excluded.owner_wxid,
                    updated_at = excluded.updated_at
                """,
                (room_id, room_name, member_count, owner_wxid, time.time()),
            )
            return True
        except Exception as e:
            logger.error("Failed to upsert group info for %s: %s", room_id, e)
            return False

    def get_group_info(self, room_id: str) -> Optional[Dict]:
        """Get group info by room_id."""
        row = self._db.execute_read_one("SELECT * FROM group_info WHERE room_id = ?", (room_id,))
        return dict(row) if row else None

    def get_all_groups(self) -> List[Dict]:
        """Get all stored group info."""
        rows = self._db.execute_read("SELECT * FROM group_info ORDER BY room_name")
        return [dict(row) for row in rows]

    # ── Statistics ────────────────────────────────────────────────────

    def get_group_stats(self, room_id: str, since: Optional[float] = None) -> Dict:
        """Get statistics for a group."""
        since_time = since or (time.time() - 86400)

        # Message count
        result = self._db.execute_read_one(
            "SELECT COUNT(*) as cnt FROM group_messages WHERE room_id = ? AND created_at >= ?",
            (room_id, since_time),
        )
        msg_count = result["cnt"] if result else 0

        # Active senders
        result = self._db.execute_read_one(
            "SELECT COUNT(DISTINCT sender_wxid) as cnt FROM group_messages WHERE room_id = ? AND created_at >= ?",
            (room_id, since_time),
        )
        active_senders = result["cnt"] if result else 0

        # Top senders
        top_rows = self._db.execute_read(
            """
            SELECT sender_wxid, sender_name, COUNT(*) as cnt
            FROM group_messages
            WHERE room_id = ? AND created_at >= ?
            GROUP BY sender_wxid ORDER BY cnt DESC LIMIT 5
            """,
            (room_id, since_time),
        )
        top_senders = [{"wxid": r["sender_wxid"], "name": r["sender_name"], "count": r["cnt"]} for r in top_rows]

        # Type distribution
        type_rows = self._db.execute_read(
            """
            SELECT msg_type, COUNT(*) as cnt
            FROM group_messages WHERE room_id = ? AND created_at >= ?
            GROUP BY msg_type ORDER BY cnt DESC
            """,
            (room_id, since_time),
        )
        type_dist = [{"type": r["msg_type"], "type_name": MessageType.name_of(r["msg_type"]), "count": r["cnt"]} for r in type_rows]

        return {
            "room_id": room_id,
            "message_count": msg_count,
            "active_senders": active_senders,
            "top_senders": top_senders,
            "type_distribution": type_dist,
        }

    # ── Maintenance ──────────────────────────────────────────────────

    def cleanup_old_messages(self, days: int = 90) -> int:
        """Delete messages older than N days."""
        cutoff = time.time() - (days * 86400)
        try:
            cursor = self._db.execute_write(
                "DELETE FROM group_messages WHERE created_at < ?", (cutoff,)
            )
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info("Cleaned up %d messages older than %d days", deleted, days)
            return deleted
        except Exception as e:
            logger.error("Cleanup failed: %s", e)
            return 0

    def vacuum(self) -> None:
        """Run VACUUM to reclaim disk space."""
        try:
            conn = self._db.get_connection()
            conn.execute("VACUUM")
            logger.info("Database vacuumed")
        except Exception as e:
            logger.error("Vacuum failed: %s", e)
