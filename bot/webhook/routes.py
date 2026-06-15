"""WebHook API routes.

All API endpoints are defined here, separated from the server setup.
Uses Flask blueprints for organization.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from flask import Blueprint, jsonify, request

if TYPE_CHECKING:
    from bot.config.loader import ConfigLoader
    from bot.db.repository import Repository
    from bot.group.filter import GroupFilter
    from bot.wcf.client import WcfClient

logger = logging.getLogger("WeChatBot.WebHook.Routes")

api_bp = Blueprint("api", __name__, url_prefix="/api")


def register_routes(
    blueprint: Blueprint,
    config_loader: "ConfigLoader",
    db: "Repository",
    group_filter: "GroupFilter",
    wcf_client: "WcfClient",
) -> None:
    """Register all API routes on the given blueprint.

    This function injects dependencies into the route handlers,
    avoiding global state and enabling testing.
    """

    @blueprint.route("/health", methods=["GET"])
    def health():
        """Health check endpoint (no auth required)."""
        return jsonify({
            "status": "ok",
            "timestamp": time.time(),
            "version": "2.0.0",
        })

    @blueprint.route("/send_group", methods=["POST"])
    def send_group():
        """Send a text message to a specified group.

        Request body (JSON):
            {
                "room_id": "xxx@chatroom",
                "content": "message text",
                "at_list": ["wxid1", "wxid2"]  // optional
            }
        """
        data = request.get_json(silent=True) or {}
        room_id = data.get("room_id")
        content = data.get("content")
        at_list = data.get("at_list", [])

        if not room_id or not content:
            return jsonify({
                "error": "Bad Request",
                "message": "Missing required fields: room_id and content",
                "code": "MISSING_FIELDS",
            }), 400

        if not room_id.endswith("@chatroom"):
            return jsonify({
                "error": "Bad Request",
                "message": f"Invalid room_id format: '{room_id}'. Must end with @chatroom",
                "code": "INVALID_ROOM_ID",
            }), 400

        try:
            if at_list:
                result = wcf_client.send_text(content, room_id, at_list=at_list)
            else:
                result = wcf_client.send_text(content, room_id)

            logger.info("WebHook: Sent message to group %s", room_id)
            return jsonify({"success": True, "result": result, "room_id": room_id})
        except Exception as e:
            logger.error("WebHook: Failed to send to group %s: %s", room_id, e)
            return jsonify({"error": "Internal Error", "message": str(e), "code": "SEND_FAILED"}), 500

    @blueprint.route("/send_admin", methods=["POST"])
    def send_admin():
        """Send a text message to the bound admin.

        Request body (JSON):
            {
                "content": "message text"
            }
        """
        data = request.get_json(silent=True) or {}
        content = data.get("content")

        if not content:
            return jsonify({
                "error": "Bad Request",
                "message": "Missing required field: content",
                "code": "MISSING_CONTENT",
            }), 400

        admin_wxid = config_loader.settings.bot.admin_wxid
        if not admin_wxid:
            return jsonify({
                "error": "Precondition Failed",
                "message": "No admin is currently bound",
                "code": "NO_ADMIN",
            }), 412

        try:
            result = wcf_client.send_text(content, admin_wxid)
            logger.info("WebHook: Sent message to admin %s", admin_wxid)
            return jsonify({"success": True, "result": result})
        except Exception as e:
            logger.error("WebHook: Failed to send to admin: %s", e)
            return jsonify({"error": "Internal Error", "message": str(e), "code": "SEND_FAILED"}), 500

    @blueprint.route("/groups", methods=["GET"])
    def list_groups():
        """List all groups with monitoring status.

        Query params:
            monitored: Filter by monitoring status (true/false)
        """
        monitored_filter = request.args.get("monitored")

        groups = db.get_all_groups()
        for g in groups:
            g["monitored"] = group_filter.is_allowed(g["room_id"])

        if monitored_filter is not None:
            monitored_val = monitored_filter.lower() == "true"
            groups = [g for g in groups if g["monitored"] == monitored_val]

        return jsonify({"groups": groups, "count": len(groups)})

    @blueprint.route("/groups/<room_id>", methods=["GET"])
    def group_detail(room_id: str):
        """Get detailed info and stats for a group."""
        info = db.get_group_info(room_id)
        if not info:
            return jsonify({"error": "Not Found", "message": f"Group {room_id} not found", "code": "GROUP_NOT_FOUND"}), 404

        stats = db.get_group_stats(room_id)
        info["monitored"] = group_filter.is_allowed(room_id)
        return jsonify({"info": info, "stats": stats})

    @blueprint.route("/messages", methods=["GET"])
    def query_messages():
        """Query messages with filters.

        Query params:
            room_id: Filter by group roomid
            sender: Filter by sender wxid
            type: Filter by message type (int)
            since: Unix timestamp start time
            until: Unix timestamp end time
            limit: Max results (default 100, max 500)
            offset: Pagination offset
        """
        room_id = request.args.get("room_id")
        sender = request.args.get("sender")
        msg_type_raw = request.args.get("type")
        since_raw = request.args.get("since")
        until_raw = request.args.get("until")
        limit = min(request.args.get("limit", default=100, type=int), 500)
        offset = request.args.get("offset", default=0, type=int)

        msg_type = int(msg_type_raw) if msg_type_raw else None
        since = float(since_raw) if since_raw else None
        until = float(until_raw) if until_raw else None

        messages = db.get_messages(
            room_id=room_id,
            sender_wxid=sender,
            start_time=since,
            end_time=until,
            msg_type=msg_type,
            limit=limit,
            offset=offset,
        )
        total = db.get_message_count(room_id=room_id, since=since)

        return jsonify({
            "messages": messages,
            "total": total,
            "limit": limit,
            "offset": offset,
        })

    @blueprint.route("/status", methods=["GET"])
    def bot_status():
        """Get bot status."""
        admin_wxid = config_loader.settings.bot.admin_wxid
        admin_contact = wcf_client.get_info_by_wxid(admin_wxid) if admin_wxid else None

        return jsonify({
            "admin": {
                "wxid": admin_wxid,
                "name": admin_contact.name if admin_contact else None,
            } if admin_wxid else None,
            "filter": {
                "mode": group_filter.mode,
                "whitelist_count": len(group_filter.whitelist),
                "blacklist_count": len(group_filter.blacklist),
            },
            "database": {
                "total_messages": db.get_message_count(),
                "total_groups": len(db.get_all_groups()),
            },
            "version": "2.0.0",
        })
