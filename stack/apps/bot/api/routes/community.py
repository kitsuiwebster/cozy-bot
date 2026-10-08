from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import asyncio
import logging
from itertools import combinations

from api.ttl_cache import TTLCache
from .top_users import (
    load_cozy_points_data, load_usernames_data, get_current_streak_from_stats,
    achievement_counts, rarity_tier,
)
from cogs.audio.sound_mappings import get_sound_display_name, normalize_sound_name
from utils.storage.couchdb_client import get_couchdb_client
from utils.audio import listener_history
from utils import first_seen

router = APIRouter()

# A sound counts as "listened" by a user once they spent this long on it.
AFFINITY_MIN_SECONDS = 600
# Pairs shared by fewer users are noise.
AFFINITY_MIN_USERS = 10


class AchievementRarity(BaseModel):
    name: str
    count: int
    percent: float
    tier: str


class StreakUser(BaseModel):
    username: str
    display_name: str
    streak: int


class StreakStats(BaseModel):
    active: int
    week_plus: int
    month_plus: int
    top: List[StreakUser]


class LevelCount(BaseModel):
    level: int
    count: int


class SoundAffinity(BaseModel):
    sound_a: str
    sound_b: str
    shared_users: int
    percent_of_a: float


class Peak(BaseModel):
    listeners: int
    date: str


class NewUsersDay(BaseModel):
    date: str
    count: int


class NewUsers(BaseModel):
    available: bool
    baseline_day: Optional[str] = None
    before_baseline: int = 0
    days: List[NewUsersDay] = []


class CommunityStats(BaseModel):
    total_users: int
    avg_session_seconds: float
    achievements: List[AchievementRarity]
    streaks: StreakStats
    levels: List[LevelCount]
    affinities: List[SoundAffinity]
    peak: Optional[Peak] = None
    new_users: NewUsers


def _name(usernames: Dict, uid: str):
    info = usernames.get(uid)
    if isinstance(info, dict):
        username = info.get('username') or f"User {uid[:8]}"
        return username, info.get('display_name') or username
    username = info or f"User {uid[:8]}"
    return username, username


def _compute() -> dict:
    users = load_cozy_points_data() or {}
    usernames = load_usernames_data() or {}
    total = len(users)

    # Achievement rarity, rarest first.
    achievements = sorted(
        (AchievementRarity(name=n, count=c, percent=round(c * 100 / total, 2), tier=rarity_tier(c * 100 / total))
         for n, c in achievement_counts(users).items()),
        key=lambda a: a.count,
    ) if total else []

    # Current streaks (a streak only counts if still alive today or yesterday).
    streaks = {uid: get_current_streak_from_stats(s) for uid, s in users.items()}
    top = sorted(((s, uid) for uid, s in streaks.items() if s > 0), reverse=True)[:10]
    streak_stats = StreakStats(
        active=sum(1 for s in streaks.values() if s > 0),
        week_plus=sum(1 for s in streaks.values() if s >= 7),
        month_plus=sum(1 for s in streaks.values() if s >= 30),
        top=[StreakUser(username=_name(usernames, uid)[0], display_name=_name(usernames, uid)[1], streak=s) for s, uid in top],
    )

    levels: Dict[int, int] = {}
    for s in users.values():
        lvl = int(s.get('level') or 1)
        levels[lvl] = levels.get(lvl, 0) + 1
    level_list = [LevelCount(level=l, count=levels.get(l, 0)) for l in range(1, max(levels, default=1) + 1)]

    sessions = sum(int(s.get('sessions_joined') or 0) for s in users.values())
    listening = sum(float(s.get('listening_time') or 0) for s in users.values())
    avg_session = round(listening / sessions, 1) if sessions else 0.0

    # Sound affinities: lift between sounds that users listened to for real.
    listened: List[set] = []
    for s in users.values():
        per_sound: Dict[str, float] = {}
        for raw, data in (s.get('listening_time_by_sound') or {}).items():
            if isinstance(data, dict):
                key = normalize_sound_name(raw)
                per_sound[key] = per_sound.get(key, 0.0) + float(data.get('total_time') or 0)
        picked = {k for k, t in per_sound.items() if t >= AFFINITY_MIN_SECONDS}
        if picked:
            listened.append(picked)
    single: Dict[str, int] = {}
    pairs: Dict[tuple, int] = {}
    for picked in listened:
        for snd in picked:
            single[snd] = single.get(snd, 0) + 1
        for a, b in combinations(sorted(picked), 2):
            pairs[(a, b)] = pairs.get((a, b), 0) + 1
    n = len(listened)
    scored = []
    for (a, b), both in pairs.items():
        if both < AFFINITY_MIN_USERS:
            continue
        lift = both * n / (single[a] * single[b])
        # Read it from the smaller audience: "X% of A listeners also love B".
        if single[a] > single[b]:
            a, b = b, a
        scored.append((lift, both, a, b))
    scored.sort(reverse=True)
    affinities = [
        SoundAffinity(sound_a=get_sound_display_name(a), sound_b=get_sound_display_name(b),
                      shared_users=both, percent_of_a=round(both * 100 / single[a], 1))
        for lift, both, a, b in scored[:6] if lift > 1
    ]

    db = get_couchdb_client()
    history = listener_history.load_history(db, days=5000)
    peak_point = max(history, key=lambda p: (p['max'], p['date']), default=None)
    peak = Peak(listeners=peak_point['max'], date=peak_point['date']) if peak_point else None

    fs = first_seen.load(db)
    if fs.get('first_seen'):
        baseline = fs.get('baseline_day')
        new_users = NewUsers(
            available=True,
            baseline_day=baseline,
            before_baseline=sum(1 for d in fs['first_seen'].values() if baseline and d <= baseline),
            days=[NewUsersDay(**d) for d in first_seen.new_users_per_day(fs)],
        )
    else:
        new_users = NewUsers(available=False)

    return CommunityStats(
        total_users=total, avg_session_seconds=avg_session, achievements=achievements,
        streaks=streak_stats, levels=level_list, affinities=affinities, peak=peak, new_users=new_users,
    ).model_dump()


# Aggregates over every user: cheap enough, but no need to redo it per page view.
_cache = TTLCache(ttl_seconds=60)


@router.get("/community-stats", response_model=CommunityStats)
async def community_stats():
    try:
        return await asyncio.to_thread(_cache.get_or_load, "community", _compute)
    except Exception:
        logging.exception("community-stats: failed to compute")
        raise HTTPException(status_code=500, detail="Internal error computing community stats")
