from fastapi import APIRouter, HTTPException
from typing import List, Optional
import sys
import os
import json
from pydantic import BaseModel

# Add project root to path to import cogs
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

router = APIRouter()

class UserStats(BaseModel):
    user_id: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    total_points: int
    rank: int

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

@router.get("/top-users", response_model=TopUsersResponse)
async def get_top_users(limit: int = 10):
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
            
            user_stats = UserStats(
                user_id=user_data['user_id'],
                username=username,
                display_name=display_name,
                total_points=user_data['total_points'],
                rank=i
            )
            users.append(user_stats)
        
        return TopUsersResponse(
            users=users,
            total_count=len(users)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching top users: {str(e)}")