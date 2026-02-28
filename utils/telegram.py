"""Telegram helpers to avoid repeated API calls."""


def get_bot_username(context) -> str:
    """Get cached bot username from bot_data (set at startup)."""
    return context.bot_data.get("bot_username", "bot")
