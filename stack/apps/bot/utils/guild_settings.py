"""Per-guild bot settings, persisted in CouchDB with an in-memory cache.

Currently a single flag per guild:
- always_on: 24/7 mode, the bot stays in the voice channel even when empty.

Reads are served from the cache (a plain dict lookup after the first load),
so hot paths like the watchdog and the auto-disconnect timer can call
is_always_on() freely. Writes are synchronous CouchDB saves: settings changes
are rare and must survive restarts.
"""

import logging
import threading

_lock = threading.Lock()
_cache = None


def _load():
    global _cache
    if _cache is None:
        try:
            from utils.storage.couchdb_client import get_couchdb_client
            _cache = get_couchdb_client().load_guild_settings()
        except Exception as e:
            logging.error(f"❌ Failed to load guild settings: {e}")
            _cache = {}
    return _cache


def preload() -> None:
    """Force-load the settings cache. Call off the event loop at startup so
    the first is_always_on() in a hot path never does blocking I/O."""
    _load()


def is_always_on(guild_id) -> bool:
    """True when 24/7 mode is enabled for this guild."""
    settings = _load().get(str(guild_id))
    return bool(settings and settings.get('always_on'))


def set_always_on(guild_id, enabled: bool) -> bool:
    """Persist the 24/7 flag for a guild. Returns False if the save failed."""
    with _lock:
        cache = _load()
        entry = cache.setdefault(str(guild_id), {})
        entry['always_on'] = bool(enabled)
        try:
            from utils.storage.couchdb_client import get_couchdb_client
            return get_couchdb_client().save_guild_settings(cache)
        except Exception as e:
            logging.error(f"❌ Failed to save guild settings: {e}")
            return False
