"""Telegram notifier for operational alerts.

Sends short messages to a Telegram chat via the Bot API. Throttles identical
messages and rate-limits the overall send rate so a log storm can't spam the
chat. All network work runs in a daemon thread, so callers never block.

Configured via env vars:
- TELEGRAM_ENABLED: "1" to enable, anything else disables silently
- TELEGRAM_BOT_TOKEN: the bot token from @BotFather
- TELEGRAM_CHAT_ID: target chat id(s), comma-separated (a user id for DMs)
"""

from __future__ import annotations

import html
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from typing import Optional


class TelegramNotifier:
    # Same exact message blocked for this many seconds. Prevents loops from
    # turning the chat into a wall of identical errors.
    THROTTLE_WINDOW_SECONDS = 300
    # Token-bucket-ish rate limit: at most RATELIMIT_MAX sends per window.
    RATELIMIT_WINDOW_SECONDS = 60
    RATELIMIT_MAX = 20
    # Telegram caps a single message at 4096 chars.
    MESSAGE_MAX_CHARS = 4096

    def __init__(self) -> None:
        self.token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
        self.chat_ids = [
            c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip()
        ]
        self.enabled = (
            os.getenv('TELEGRAM_ENABLED', '0') == '1'
            and bool(self.token)
            and bool(self.chat_ids)
        )
        self._recent: dict[str, float] = {}
        self._sends: deque[float] = deque()
        self._lock = threading.Lock()

    def send(self, text: str, parse_mode: str = 'HTML') -> bool:
        """Queue a send. Returns True if accepted, False if dropped (disabled, throttled, or rate-limited)."""
        if not self.enabled or not text:
            return False

        now = time.monotonic()

        with self._lock:
            last = self._recent.get(text)
            if last is not None and (now - last) < self.THROTTLE_WINDOW_SECONDS:
                return False

            while self._sends and (now - self._sends[0]) > self.RATELIMIT_WINDOW_SECONDS:
                self._sends.popleft()
            if len(self._sends) >= self.RATELIMIT_MAX:
                return False

            self._sends.append(now)
            self._recent[text] = now

            # Cheap GC: prune throttle table when it grows
            if len(self._recent) > 200:
                cutoff = now - self.THROTTLE_WINDOW_SECONDS
                self._recent = {k: v for k, v in self._recent.items() if v > cutoff}

        threading.Thread(
            target=self._post,
            args=(text[: self.MESSAGE_MAX_CHARS], parse_mode),
            daemon=True,
            name='telegram-send',
        ).start()
        return True

    def _post(self, text: str, parse_mode: str) -> None:
        url = f'https://api.telegram.org/bot{self.token}/sendMessage'
        # Log under 'telegram.*' so the handler can filter its own messages and
        # avoid an infinite recursion loop on failures.
        log = logging.getLogger('telegram.notifier')
        for chat_id in self.chat_ids:
            payload = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True,
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            try:
                with urllib.request.urlopen(req, timeout=5):
                    continue
            except urllib.error.HTTPError as e:
                log.error('telegram send rejected: %s %s', e.code, e.reason)
            except Exception as e:
                log.error('telegram send failed: %s', e)


_notifier: Optional[TelegramNotifier] = None


def get_notifier() -> TelegramNotifier:
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier


def notify(text: str, parse_mode: str = 'HTML') -> bool:
    return get_notifier().send(text, parse_mode=parse_mode)


def escape(s: str) -> str:
    """HTML-escape a string for safe inclusion in a Telegram HTML message."""
    return html.escape(s, quote=False)
