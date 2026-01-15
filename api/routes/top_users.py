from fastapi import APIRouter, HTTPException
from typing import List, Optional
import sys
import os
import json
from pydantic import BaseModel

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

# Response model for top users list
class TopUsersResponse(BaseModel):
    users: List[UserStats]
    total_count: int

# Load cozy points data with encryption support
def load_cozy_points_data():
    # Try to import encryption utilities
    try:
        from utils.encryption import encryption
        data = encryption.load_encrypted_json('data/cozy_points.json')
        if data:
            return data
    except ImportError:
        pass
    
    # Fallback to standard JSON loading
    data_file = 'data/cozy_points.json'
    try:
        with open(data_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

# Load usernames cache with encryption support
def load_usernames_data():
    # Try to import encryption utilities
    try:
        from utils.encryption import encryption
        data = encryption.load_encrypted_json('data/usernames.json')
        if data:
            return data
    except ImportError:
        pass
    
    # Fallback to standard JSON loading
    data_file = 'data/usernames.json'
    try:
        with open(data_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
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
    total_time: float
    formatted_time: str
    session_count: int

# Response model for user's sound statistics
class UserSoundStats(BaseModel):
    user_id: str
    username: Optional[str] = None
    favorite_sound: Optional[str] = None
    sounds: List[SoundStats]

# Convert sound filename to emoji display name
def get_sound_display_name(sound_filename: str) -> str:
    sound_mapping = {
        'rain00.mp3': '🌧️💧⚡',
        'rain01.mp3': '🌧️🌿🌙',
        'rain02.mp3': '🌧️⛈️💨',
        'rain03.mp3': '🌧️🏠🔥',
        'rain04.mp3': '🌧️🚗⚡',
        'sea00.mp3': '🌊💧💦',
        'sea01.mp3': '🌊🕊️⛱️',
        'sea02.mp3': '🌊🏝️🌙',
        'sea03.mp3': '🌊⛵🕊️',
        'sea04.mp3': '🌊🤿🔱',
        'sparkles00.mp3': '✨🪄⭐',
        'sparkles01.mp3': '✨🌟💫',
        'sparkles02.mp3': '✨🪄💎',
        'sparkles03.mp3': '✨🌲🌙',
        'sparkles04.mp3': '✨🪄💫',
        'background-music00.mp3': '🎶🏛️🌙',
        'background-music01.mp3': '🎶🍃🌩️',
        'background-music02.mp3': '🎶🏺💦',
        'background-music03.mp3': '🎶🌸💦',
        'background-music04.mp3': '🎶🌿💦',
        'white-noise00.mp3': '🤍⏳🔜',
        'white-noise01.mp3': '🤍🌌🌕',
        'white-noise02.mp3': '🤍⏳🔜',
        'white-noise03.mp3': '🤍⏳🔜',
        'white-noise04.mp3': '🤍⏳🔜',
    }
    return sound_mapping.get(sound_filename, sound_filename)

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
async def get_top_sounds(limit: int = None):
    try:
        user_data = load_cozy_points_data()
        
        # Aggregate all sound data across users
        sound_aggregates = {}
        
        for user_id, user_stats in user_data.items():
            listening_times = user_stats.get('listening_time_by_sound', {})
            
            for sound_name, sound_data in listening_times.items():
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
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching top sounds: {str(e)}")

# Get top users by cozy points
@router.get("/top-users", response_model=TopUsersResponse)
async def get_top_users(limit: int = None):
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
            
            # Get current valid streak (respects 24h rule)
            current_streak = cozy_gamification.get_current_streak(user_data['user_id'])
            
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
                favorite_sound=favorite_sound_emoji
            )
            users.append(user_stats)
        
        return TopUsersResponse(
            users=users,
            total_count=len(users)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching top users: {str(e)}")