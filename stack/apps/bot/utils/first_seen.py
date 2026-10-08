"""First day each user was seen, for the new-users-per-day stat.

A single document (`stats:first_seen`) maps user id -> 'YYYY-MM-DD'. The bot
records a user the first time it creates their stats (join_session, bot
process only, so a single writer). Users older than the tracking were
backfilled from the daily offsite backups: those already present in the
oldest backup (`baseline_day`) only mean "on or before" that day, so they are
not counted as new users of that day.
"""

import logging
import threading
from datetime import datetime, timezone

DOC_ID = 'stats:first_seen'
_lock = threading.Lock()
_doc = None


def _today():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _clean(doc):
    return {k: v for k, v in (doc or {}).items() if not k.startswith('_') and k not in ('created_at', 'updated_at')}


def load(db):
    """The stored document: {'first_seen': {user_id: day}, 'baseline_day', 'tracking_since'}."""
    return _clean(db.get_document(db.db, DOC_ID))


def record(db, user_id):
    """Remember today as the first day of a user not seen before. Never overwrites."""
    global _doc
    try:
        with _lock:
            if _doc is None:
                _doc = load(db)
            seen = _doc.setdefault('first_seen', {})
            if user_id in seen:
                return
            seen[user_id] = _today()
            _doc.setdefault('tracking_since', _today())
            _doc['type'] = 'stats'
            snapshot = {**_doc, 'first_seen': dict(seen)}
        db.save_document(db.db, DOC_ID, snapshot)
    except Exception as e:
        logging.error(f"❌ Failed to record first-seen day for {user_id}: {e}")


def new_users_per_day(doc):
    """[{'date', 'count'}] oldest first, leaving out users dated at the baseline."""
    baseline = doc.get('baseline_day')
    counts = {}
    for day in (doc.get('first_seen') or {}).values():
        if baseline and day <= baseline:
            continue
        counts[day] = counts.get(day, 0) + 1
    return [{'date': d, 'count': counts[d]} for d in sorted(counts)]
