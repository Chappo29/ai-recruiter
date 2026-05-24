"""
Backward-compatible facade.

- Outbound messages: stateless, use from FastAPI (pass db session).
- Polling: only in bot-worker (`python -m bot`), see bot.polling.
"""

from bot.outbound import get_bot_token, send_message, send_rejection

__all__ = [
    "get_bot_token",
    "send_message",
    "send_rejection",
]
