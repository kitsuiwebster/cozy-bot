from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import sys
import os
import json
from pydantic import BaseModel

# Cap user-supplied list sizes to prevent unbounded responses
MAX_TOP_LIMIT = 1000

# Add project root to path to import cogs
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cogs.stats.gamification import cozy_gamification

# Initialize FastAPI router for user stats endpoints
router = APIRouter()

# Response model for individual user stats
class UserStats(BaseModel):
    user_id: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    total_points: int
    rank: int
    listening_time_seconds: float
    listening_time_formatted: str  # Format humain "2h 30m"
    daily_streak: int
    level: int
    level_progress: float
    sessions_joined: int
    achievements_count: int
    favorite_sound: Optional[str] = None
    days_since_last_activity: Optional[int] = None

# Response model for top users list
class TopUsersResponse(BaseModel):
    users: List[UserStats]
    total_count: int

# Load cozy points data from CouchDB
def load_cozy_points_data():
    try:
        from utils.storage.couchdb_client import get_couchdb_client
        db = get_couchdb_client()
        return db.load_user_data()
    except Exception:
        return {}

# Load usernames cache from CouchDB
def load_usernames_data():
    try:
        from utils.storage.couchdb_client import get_couchdb_client
        db = get_couchdb_client()
        return db.load_usernames()
    except Exception:
        return {}

# Convert seconds to human-readable listening time format
def format_listening_time(total_seconds: float) -> str:
    if total_seconds < 60:
        return f"{int(total_seconds)}s"
    elif total_seconds < 3600:
        minutes = int(total_seconds / 60)
        seconds = int(total_seconds % 60)
        return f"{minutes}m {seconds}s" if seconds > 0 else f"{minutes}m"
    else:
        hours = int(total_seconds / 3600)
        minutes = int((total_seconds % 3600) / 60)
        return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"

# Response model for individual sound statistics
class SoundStats(BaseModel):
    sound_name: str
    display_name: str
    total_time: float
    formatted_time: str
    session_count: int

# Response model for user's sound statistics
class UserSoundStats(BaseModel):
    user_id: str
    username: Optional[str] = None
    favorite_sound: Optional[str] = None
    sounds: List[SoundStats]

# Response model for current sound being played
class CurrentSound(BaseModel):
    name: str
    display_name: str
    started_at: str
    duration_seconds: int

# Response model for detailed user profile
class UserDetailedProfile(BaseModel):
    user_id: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    total_points: int
    rank: Optional[int] = None
    level: int
    level_progress: float
    listening_time_seconds: float
    listening_time_formatted: str
    daily_streak: int
    sessions_joined: int
    days_since_last_activity: Optional[int] = None
    last_join_time: Optional[str] = None
    last_active_date: Optional[str] = None
    achievements: List[str]
    category_completions: List[str]
    favorite_sound: Optional[str] = None
    listening_by_sound: List[SoundStats]
    current_sound: Optional[CurrentSound] = None

# Import centralized sound mapping
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from cogs.audio.sound_mappings import get_sound_display_name, normalize_sound_name

# Response model for top sound statistics
class TopSoundStats(BaseModel):
    sound_name: str
    display_name: str
    total_time: float
    formatted_time: str
    total_sessions: int
    unique_listeners: int

# Response model for top sounds list
class TopSoundsResponse(BaseModel):
    sounds: List[TopSoundStats]
    total_sounds: int

# Get most listened sounds globally
@router.get("/top-sounds", response_model=TopSoundsResponse)
async def get_top_sounds(limit: Optional[int] = Query(default=None, ge=1, le=MAX_TOP_LIMIT)):
    try:
        user_data = load_cozy_points_data()
        
        # Aggregate all sound data across users
        sound_aggregates = {}
        
        for user_id, user_stats in user_data.items():
            listening_times = user_stats.get('listening_time_by_sound', {})
            
            for sound_name, sound_data in listening_times.items():
                sound_name = normalize_sound_name(sound_name)
                if sound_name not in sound_aggregates:
                    sound_aggregates[sound_name] = {
                        'total_time': 0.0,
                        'total_sessions': 0,
                        'unique_listeners': set()
                    }
                
                # Safe access to sound_data with type validation
                if isinstance(sound_data, dict):
                    sound_aggregates[sound_name]['total_time'] += sound_data.get('total_time', 0.0)
                    sound_aggregates[sound_name]['total_sessions'] += sound_data.get('session_count', 0)
                    sound_aggregates[sound_name]['unique_listeners'].add(user_id)
        
        # Convert to list and sort by total time
        sounds_list = []
        for sound_name, data in sound_aggregates.items():
            sounds_list.append(TopSoundStats(
                sound_name=sound_name,
                display_name=get_sound_display_name(sound_name),
                total_time=data['total_time'],
                formatted_time=format_listening_time(data['total_time']),
                total_sessions=data['total_sessions'],
                unique_listeners=len(data['unique_listeners'])
            ))
        
        # Sort by total time descending
        sounds_list.sort(key=lambda x: x.total_time, reverse=True)
        
        # Apply limit
        if limit:
            sounds_list = sounds_list[:limit]
        
        return TopSoundsResponse(
            sounds=sounds_list,
            total_sounds=len(sounds_list)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching top sounds: {str(e)}")

# Compute streak from provided stats to avoid stale in-memory cache
def get_current_streak_from_stats(user_stats: dict) -> int:
    last_active = user_stats.get('last_active_date')
    if not last_active:
        return 0
    try:
        from datetime import datetime
        last = datetime.strptime(last_active, '%Y-%m-%d')
        today = datetime.now()
        days_diff = (today - last).days
        if days_diff <= 1:
            streak = user_stats.get('daily_streak', 0)
            return 1 if streak <= 0 else streak
    except Exception:
        return 0
    return 0

# Get top users by cozy points
@router.get("/top-users", response_model=TopUsersResponse)
async def get_top_users(limit: Optional[int] = Query(default=None, ge=1, le=MAX_TOP_LIMIT)):
    try:
        # Load data directly from the same JSON files the bot uses
        user_data_raw = load_cozy_points_data()
        usernames_data = load_usernames_data()
        
        if not user_data_raw:
            return TopUsersResponse(users=[], total_count=0)
        
        # Create leaderboard format
        users_list = []
        for user_id, stats in user_data_raw.items():
            users_list.append({
                'user_id': user_id,
                'total_points': stats.get('total_points', 0),
                'level': stats.get('level', 1),
                'listening_time': stats.get('listening_time', 0),
                'achievements_count': len(stats.get('achievements', [])),
                'daily_streak': stats.get('daily_streak', 0)
            })
        
        # Sort by points descending and limit
        users_list.sort(key=lambda x: x['total_points'], reverse=True)
        if limit:
            users_list = users_list[:limit]
        
        # Format response
        users = []
        for i, user_data in enumerate(users_list, start=1):
            # Get cached usernames from separate file or fallback to user ID
            user_info = usernames_data.get(user_data['user_id'])
            
            if isinstance(user_info, dict):
                # New format with both username and display_name
                username = user_info.get('username', f"User {user_data['user_id'][:8]}")
                display_name = user_info.get('display_name', username)
            else:
                # Old format or fallback
                username = user_info if user_info else f"User {user_data['user_id'][:8]}"
                display_name = username
            
            # Get original user data for additional stats
            original_stats = user_data_raw.get(user_data['user_id'], {})
            listening_time_seconds = original_stats.get('listening_time', 0.0)
            
            # Get current valid streak from fresh user stats (respects 24h rule)
            current_streak = get_current_streak_from_stats(original_stats)
            
            # Get favorite sound (most listened sound)
            favorite_sound_emoji = None
            listening_times = original_stats.get('listening_time_by_sound', {})
            if listening_times:
                # Find sound with most total_time
                max_time = 0
                favorite_sound = None
                for sound_name, sound_data in listening_times.items():
                    if isinstance(sound_data, dict):
                        sound_time = sound_data.get('total_time', 0.0)
                        if sound_time > max_time:
                            max_time = sound_time
                            favorite_sound = sound_name
                
                if favorite_sound:
                    favorite_sound_emoji = get_sound_display_name(favorite_sound)

            # Calculate days since last activity
            days_since_last_activity = None
            last_active_date = original_stats.get('last_active_date')
            if last_active_date:
                try:
                    from datetime import datetime
                    last_active = datetime.strptime(last_active_date, '%Y-%m-%d')
                    today = datetime.now()
                    days_since_last_activity = (today - last_active).days
                except Exception:
                    days_since_last_activity = None

            user_stats = UserStats(
                user_id=user_data['user_id'],
                username=username,
                display_name=display_name,
                total_points=user_data['total_points'],
                rank=i,
                listening_time_seconds=listening_time_seconds,
                listening_time_formatted=format_listening_time(listening_time_seconds),
                daily_streak=current_streak,
                level=original_stats.get('level', 1),
                level_progress=original_stats.get('level_progress', 0.0),
                sessions_joined=original_stats.get('sessions_joined', 0),
                achievements_count=len(original_stats.get('achievements', [])),
                favorite_sound=favorite_sound_emoji,
                days_since_last_activity=days_since_last_activity
            )
            users.append(user_stats)
        
        return TopUsersResponse(
            users=users,
            total_count=len(users)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching top users: {str(e)}")

# Get detailed profile for a specific user by username
@router.get("/user/{username}", response_model=UserDetailedProfile)
async def get_user_profile(username: str):
    try:
        from datetime import datetime

        # Load data
        user_data_raw = load_cozy_points_data()
        usernames_data = load_usernames_data()

        # Find user by username
        user_id = None
        for uid, user_info in usernames_data.items():
            if isinstance(user_info, dict):
                if user_info.get('username', '').lower() == username.lower():
                    user_id = uid
                    break
            elif isinstance(user_info, str):
                if user_info.lower() == username.lower():
                    user_id = uid
                    break

        if not user_id:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found")

        if user_id not in user_data_raw:
            raise HTTPException(status_code=404, detail=f"User data not found for '{username}'")

        user_stats = user_data_raw[user_id]

        # Get username and display_name
        user_info = usernames_data.get(user_id)
        if isinstance(user_info, dict):
            username_str = user_info.get('username', f"User {user_id[:8]}")
            display_name = user_info.get('display_name', username_str)
        else:
            username_str = user_info if user_info else f"User {user_id[:8]}"
            display_name = username_str

        # Calculate rank (position in leaderboard)
        all_users = [(uid, stats.get('total_points', 0)) for uid, stats in user_data_raw.items()]
        all_users.sort(key=lambda x: x[1], reverse=True)
        rank = None
        for i, (uid, _) in enumerate(all_users, start=1):
            if uid == user_id:
                rank = i
                break

        # Get current valid streak from fresh user stats
        current_streak = get_current_streak_from_stats(user_stats)

        # Calculate days since last activity
        days_since_last_activity = None
        last_active_date = user_stats.get('last_active_date')
        if last_active_date:
            try:
                last_active = datetime.strptime(last_active_date, '%Y-%m-%d')
                today = datetime.now()
                days_since_last_activity = (today - last_active).days
            except Exception:
                days_since_last_activity = None

        # Get achievements (full list)
        achievements = user_stats.get('achievements', [])

        # Get category completions
        category_completions = user_stats.get('category_completions', [])

        # Get listening_by_sound details
        listening_by_sound = []
        listening_times = user_stats.get('listening_time_by_sound', {})
        sound_rollup = {}
        for sound_name, sound_data in listening_times.items():
            if isinstance(sound_data, dict):
                normalized_name = normalize_sound_name(sound_name)
                if normalized_name not in sound_rollup:
                    sound_rollup[normalized_name] = {
                        'total_time': 0.0,
                        'session_count': 0
                    }
                sound_rollup[normalized_name]['total_time'] += sound_data.get('total_time', 0.0)
                sound_rollup[normalized_name]['session_count'] += sound_data.get('session_count', 0)

        for sound_name, data in sound_rollup.items():
            listening_by_sound.append(SoundStats(
                sound_name=sound_name,
                display_name=get_sound_display_name(sound_name),
                total_time=data['total_time'],
                formatted_time=format_listening_time(data['total_time']),
                session_count=data['session_count']
            ))

        # Sort by total time descending
        listening_by_sound.sort(key=lambda x: x.total_time, reverse=True)

        # Get favorite sound (top 1)
        favorite_sound_emoji = None
        if listening_by_sound:
            favorite_sound_emoji = get_sound_display_name(listening_by_sound[0].sound_name)

        # Get current sound if actively listening
        current_sound_obj = None
        current_sound = user_stats.get('current_sound')
        if current_sound and isinstance(current_sound, dict) and 'start_time' in current_sound:
            try:
                start_time = datetime.fromisoformat(current_sound['start_time'])
                duration = int((datetime.now() - start_time).total_seconds())
                normalized_name = normalize_sound_name(current_sound['name'])
                current_sound_obj = CurrentSound(
                    name=normalized_name,
                    display_name=get_sound_display_name(normalized_name),
                    started_at=current_sound['start_time'],
                    duration_seconds=duration
                )
            except Exception:
                current_sound_obj = None

        return UserDetailedProfile(
            user_id=user_id,
            username=username_str,
            display_name=display_name,
            total_points=user_stats.get('total_points', 0),
            rank=rank,
            level=user_stats.get('level', 1),
            level_progress=user_stats.get('level_progress', 0.0),
            listening_time_seconds=user_stats.get('listening_time', 0.0),
            listening_time_formatted=format_listening_time(user_stats.get('listening_time', 0.0)),
            daily_streak=current_streak,
            sessions_joined=user_stats.get('sessions_joined', 0),
            days_since_last_activity=days_since_last_activity,
            last_join_time=user_stats.get('last_join_time'),
            last_active_date=last_active_date,
            achievements=achievements,
            category_completions=category_completions,
            favorite_sound=favorite_sound_emoji,
            listening_by_sound=listening_by_sound,
            current_sound=current_sound_obj
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user profile: {str(e)}")
