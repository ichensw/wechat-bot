#!/usr/bin/env python3
"""WeChat Bot v2.0 - A production-grade WeChatFerry-based monitoring bot.

Runs exclusively on Windows with WeChat 3.9.12.51 installed.

Usage:
  python main.py                          Start with default config
  python main.py -c /path/to/config.yaml  Start with custom config
  python main.py --check                  Check WeChat login status
  python main.py --init                   Create a default config file
  python main.py --version                Show version

Environment Variables:
  WEBHOOK_TOKEN         WebHook API authentication token
  LOG_LEVEL             Logging level (DEBUG/INFO/WARNING/ERROR)
"""

from __future__ import annotations

import argparse
import os
import sys

from bot import __version__


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="WeChatBot v2.0 - WeChatFerry-based monitoring bot (Windows only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                            Start the bot
  python main.py -c my_config.yaml          Custom config
  python main.py --check                    Check WeChat login
  python main.py --init                     Create default config

Admin Commands (via WeChat private message):
  #绑定管理员          Bind yourself as admin
  #帮助                Show all commands

WebHook API:
  curl -H "Authorization: Bearer <token>" http://localhost:8080/api/status
        """,
    )
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Configuration file path (default: config.yaml)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if WeChat is logged in and exit",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Create a default configuration file",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"WeChatBot v{__version__}",
    )

    args = parser.parse_args()

    if args.init:
        _create_default_config(args.config)
        return

    if args.check:
        _check_login(args.config)
        return

    # Start the bot
    _start_bot(args.config)


def _create_default_config(path: str) -> None:
    """Create a default configuration file."""
    if os.path.exists(path):
        print(f"❌ Config file already exists: {path}")
        print("   Remove it first or use a different path: python main.py --init -c my_config.yaml")
        sys.exit(1)

    import shutil
    default_config = os.path.join(os.path.dirname(__file__), "config.yaml")
    if os.path.exists(default_config):
        shutil.copy2(default_config, path)
        print(f"✅ Default config created: {path}")
        print("   Edit it before starting the bot!")
    else:
        print(f"❌ Default config template not found at {default_config}")
        sys.exit(1)


def _check_login(config_path: str) -> None:
    """Check if WeChat is logged in."""
    try:
        from bot.config.loader import ConfigLoader
        from bot.utils.logger import setup_logging

        loader = ConfigLoader(config_path)
        settings = loader.load()
        setup_logging(settings.logging)

        from bot.wcf.client import create_wcf_client

        client = create_wcf_client()
        client.connect()

        if client.is_login():
            info = client.get_user_info()
            print("✅ WeChat is logged in!")
            print(f"   wxid:   {info.wxid}")
            print(f"   name:   {info.name}")
            print(f"   mobile: {info.mobile}")
        else:
            print("❌ WeChat is NOT logged in. Please login first.")

        client.disconnect()
    except Exception as e:
        print(f"❌ Failed to check login: {e}")
        print("   Make sure WeChat is running and wcferry is installed.")
        sys.exit(1)


def _start_bot(config_path: str) -> None:
    """Start the bot."""
    from bot.core.bot import WeChatBot

    bot = WeChatBot(config_path)
    bot.start()


if __name__ == "__main__":
    main()
