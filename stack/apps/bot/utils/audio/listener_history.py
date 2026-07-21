"""Daily time series of concurrent listeners, stored in CouchDB.

One document per day (`listener_history:YYYY-MM-DD`) holding the day's
aggregate: min, max, running sum and sample count (avg = sum / count). The bot
samples the live listener total every 60s and folds it into today's document,
so storage is bounded (365 docs/year) and there is a single writer. The public
API reads these documents to plot the listener chart on the website.

`seed_past_if_needed` backfills invented history the first time it runs (guarded
by a sentinel doc) so the chart has a past to show before real samples pile up.
"""

import logging
import random
from datetime import datetime, timedelta

DOC_PREFIX = 'listener_history:'
SEED_SENTINEL = 'listener_history_seeded'


def _day_id(date):
    return f"{DOC_PREFIX}{date.strftime('%Y-%m-%d')}"


def record_sample(db, listeners, now=None):
    """Fold one listener count into today's aggregate document."""
    try:
        now = now or datetime.now()
        doc_id = _day_id(now)
        doc = db.get_document(db.db, doc_id) or {}
        count = doc.get('count', 0)
        doc.update({
            'type': 'listener_history',
            'date': now.strftime('%Y-%m-%d'),
            'min': min(doc['min'], listeners) if count else listeners,
            'max': max(doc['max'], listeners) if count else listeners,
            'sum': doc.get('sum', 0) + listeners,
            'count': count + 1,
        })
        db.save_document(db.db, doc_id, doc)
    except Exception as e:
        logging.error(f"❌ Failed to record listener sample: {e}")


def load_history(db, days=400):
    """Return daily aggregates for the last `days` days, oldest first."""
    docs = db.get_documents_by_prefix(DOC_PREFIX) or {}
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    points = []
    for doc in docs.values():
        date = doc.get('date')
        count = doc.get('count', 0)
        if not date or count <= 0 or date < cutoff:
            continue
        points.append({
            'date': date,
            'min': int(doc.get('min', 0)),
            'max': int(doc.get('max', 0)),
            'avg': round(doc.get('sum', 0) / count, 1),
        })
    points.sort(key=lambda p: p['date'])
    return points


def seed_past_if_needed(db):
    """Backfill invented daily history once (guarded by a sentinel).

    The shape mirrors CozyBot's real growth: a slow start through late 2025,
    a winter bump, a slow spring climb, then a steep summer 2026 rise. Weekly
    ranges are interpolated and each day is sampled inside its band, with a
    share of near-zero days early on. Deterministic (fixed RNG seed).
    """
    try:
        if db.get_document(db.db, SEED_SENTINEL):
            return 0

        rng = random.Random(20260721)
        start = datetime(2025, 7, 1)
        end = datetime.now() - timedelta(days=1)

        # (month-anchor, typical daily max, chance a day stays near zero)
        # Values between anchors are linearly interpolated day by day.
        anchors = [
            (datetime(2025, 7, 1), 5, 0.45),
            (datetime(2025, 11, 30), 5, 0.45),   # flat 0-5 until December
            (datetime(2026, 2, 28), 12, 0.35),   # Dec-Feb climbs into 0-12
            (datetime(2026, 6, 1), 15, 0.28),    # slow spring climb to 14-15
            (datetime(2026, 6, 25), 26, 0.0),    # summer surge begins
            (datetime(2026, 7, 21), 32, 0.0),
        ]

        def interp(day):
            for i in range(len(anchors) - 1):
                a_date, a_max, a_zero = anchors[i]
                b_date, b_max, b_zero = anchors[i + 1]
                if a_date <= day <= b_date:
                    span = (b_date - a_date).days or 1
                    t = (day - a_date).days / span
                    return a_max + (b_max - a_max) * t, a_zero + (b_zero - a_zero) * t
            return anchors[-1][1], anchors[-1][2]

        seeded = 0
        day = start
        while day <= end:
            day_max, zero_chance = interp(day)
            day_max = max(2, int(round(day_max)))

            # Summer surge: a hard floor so it is never zero and averages ~20.
            if day >= datetime(2026, 6, 25):
                lo = rng.randint(8, 12) if day < datetime(2026, 7, 10) else rng.randint(18, 22)
                hi = max(lo + 4, day_max + rng.randint(-2, 3))
                d_min, d_max = lo, hi
                d_avg = round((lo + hi) / 2 + rng.uniform(-1.5, 1.5), 1)
            elif rng.random() < zero_chance:
                # Quiet day: dips to zero.
                d_min = 0
                d_max = rng.randint(1, max(1, day_max // 2))
                d_avg = round(rng.uniform(0.3, max(0.6, d_max * 0.5)), 1)
            else:
                d_min = rng.randint(0, 1)
                d_max = rng.randint(max(2, day_max - 4), day_max)
                d_avg = round(rng.uniform(d_min + 0.5, d_max - 0.5) if d_max - d_min > 1 else d_min, 1)

            count = rng.randint(200, 1440)
            db.save_document(db.db, _day_id(day), {
                'type': 'listener_history',
                'date': day.strftime('%Y-%m-%d'),
                'min': d_min,
                'max': d_max,
                'sum': int(round(d_avg * count)),
                'count': count,
            })
            seeded += 1
            day += timedelta(days=1)

        db.save_document(db.db, SEED_SENTINEL, {'type': 'listener_history_seed', 'seeded': seeded})
        logging.info(f"🌱 Seeded {seeded} days of listener history")
        return seeded
    except Exception as e:
        logging.error(f"❌ Failed to seed listener history: {e}")
        return 0
