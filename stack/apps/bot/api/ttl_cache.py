import threading
import time


# Small in-process cache for slow-moving, read-only public API data (leaderboards,
# server names). Only use it for pure reads: never from a path that reads, modifies
# and writes back (admin routes, CouchDBClient), or a stale copy would overwrite
# newer data in CouchDB.
class TTLCache:
    def __init__(self, ttl_seconds: float = 60.0):
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._entries = {}

    def get_or_load(self, key, loader):
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry and entry[1] > now:
                return entry[0]

        value = loader()
        # Loaders return {} on CouchDB errors; don't pin a failure for a full TTL
        if value:
            with self._lock:
                self._entries[key] = (value, time.monotonic() + self._ttl)
        return value
