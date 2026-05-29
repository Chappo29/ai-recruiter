"""Telegram bot middleware (python-telegram-bot)."""

import logging
import time

from telegram import Update
from telegram.ext import ApplicationHandlerStop, BaseHandler, ContextTypes

logger = logging.getLogger(__name__)


class ThrottleHandler(BaseHandler[Update, ContextTypes.DEFAULT_TYPE, None]):
    """
    Drop updates if the same user sends messages faster than rate_limit seconds.

    Prevents burst traffic → Telegram flood control → handler/session cascades.
    """

    def __init__(self, rate_limit: float = 1.0):
        super().__init__(self._handle, block=True)
        self._rate_limit = max(0.1, rate_limit)
        self._last_seen: dict[int, float] = {}

    def check_update(self, update: object) -> bool:
        if not isinstance(update, Update):
            return False
        if update.effective_user is None:
            return False
        if isinstance(update, Update) and update.message and update.message.text:
            text = update.message.text.strip()
            if text.startswith("/"):
                return False
        return bool(update.message or update.callback_query)

    async def _handle(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id  # type: ignore[union-attr]
        now = time.monotonic()
        last = self._last_seen.get(user_id, 0.0)

        if now - last < self._rate_limit:
            logger.debug("Throttled user %s (%.2fs since last message)", user_id, now - last)
            raise ApplicationHandlerStop()

        self._last_seen[user_id] = now

        # Prevent unbounded memory growth
        if len(self._last_seen) > 10_000:
            cutoff = now - self._rate_limit * 2
            self._last_seen = {
                uid: ts for uid, ts in self._last_seen.items() if ts >= cutoff
            }
