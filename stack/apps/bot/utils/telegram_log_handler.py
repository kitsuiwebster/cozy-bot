"""Logging handler that forwards WARNING+ records to Telegram.

Attaches to the root logger so any module's ``logging.warning/error/exception``
call ends up as a Telegram notification. The notifier itself logs under the
``telegram.*`` namespace; those records are skipped here to avoid a loop where
a failed Telegram send re-triggers another send.
"""

from __future__ import annotations

import logging

from .telegram_notifier import escape, notify


class TelegramLogHandler(logging.Handler):
    LEVEL_EMOJI = {
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '💥',
    }

    def emit(self, record: logging.LogRecord) -> None:
        # Don't forward our own telegram-notifier messages — would loop on failure.
        if record.name.startswith('telegram'):
            return
        try:
            emoji = self.LEVEL_EMOJI.get(record.levelname, '📝')
            msg = self.format(record)
            # 3800 leaves headroom under Telegram's 4096-char cap for the header.
            body = escape(msg)[:3800]
            text = f'{emoji} <b>{record.levelname}</b>\n<pre>{body}</pre>'
            # Alert bucket: never starved by informational pings.
            notify(text, priority=True)
        except Exception:
            self.handleError(record)
