from fastapi import APIRouter, HTTPException
from typing import List, Optional
import sys
import os
import json
from pydantic import BaseModel

# Add project root to path to import cogs
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cogs.stats.gamification import cozy_gamification

router = APIRouter()

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

class TopUsersResponse(BaseModel):
    users: List[UserStats]
    total_count: int

def load_cozy_points_data():
    """Load cozy points data directly from JSON file"""
    data_file = 'data/cozy_points.json'
    try:
        with open(data_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def load_usernames_data():
    """Load usernames cache from JSON file"""
    data_file = 'data/usernames.json'
    try:
        with open(data_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def format_listening_time(total_seconds: float) -> str:
    """Convert seconds to human-readable listening time format"""
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

@router.get("/top-users", response_model=TopUsersResponse)
async def get_top_users(limit: int = None):
    """Get top users by cozy points"""
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
                'total_points': stats['total_points'],
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
            
            # Get current valid streak (0 if not active today)
            current_streak = cozy_gamification.get_current_streak(user_data['user_id'])
            
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
                achievements_count=len(original_stats.get('achievements', []))
            )
            users.append(user_stats)
        
        return TopUsersResponse(
            users=users,
            total_count=len(users)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching top users: {str(e)}")