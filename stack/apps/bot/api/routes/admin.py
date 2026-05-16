from fastapi import APIRouter, HTTPException, Depends, Header, Query
from typing import Optional
import sys
import os
import json
import logging
from pydantic import BaseModel, Field

# Reasonable bounds for points/seconds payloads — prevents nonsense like INT_MIN
MAX_POINTS = 1_000_000
MAX_SECONDS = 31_536_000  # 1 year in seconds
MAX_DEBUG_PAGE_SIZE = 1000

# Add project root to path to import cogs
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cogs.stats.gamification import cozy_gamification

# Initialize FastAPI router for admin endpoints
router = APIRouter()

# Load server voice time data (prefer CouchDB, fallback to disk)
def load_voice_time_data():
    try:
        from utils.storage.couchdb_client import get_couchdb_client
        db = get_couchdb_client()
        return db.load_voice_time_data()
    except Exception:
        try:
            with open('data/voice_time_data.json', 'r') as f:
                return json.load(f)
        except Exception:
            return {}

# Save server voice time data (prefer CouchDB, fallback to disk)
def save_voice_time_data(data):
    try:
        from utils.storage.couchdb_client import get_couchdb_client
        db = get_couchdb_client()
        return db.save_voice_time_data(data)
    except Exception:
        try:
            os.makedirs('data', exist_ok=True)
            with open('data/voice_time_data.json', 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False

# Find server name by guild_id from the servernames cache
def get_server_name_by_id(guild_id: str) -> Optional[str]:
    try:
        server_info = cozy_gamification.servernames.get(guild_id)
        if isinstance(server_info, dict):
            return server_info.get('name', f'Server {guild_id[:8]}')
        elif isinstance(server_info, str):
            return server_info
        return f'Server {guild_id[:8]}'
    except Exception:
        return f'Server {guild_id[:8]}'

# Find user_id by username from the usernames cache
def get_user_id_by_username(username: str) -> Optional[str]:
    try:
        # Search through usernames data to find matching username
        for user_id, user_info in cozy_gamification.usernames.items():
            if isinstance(user_info, dict):
                if user_info.get('username', '').lower() == username.lower():
                    return user_id
            elif isinstance(user_info, str):
                if user_info.lower() == username.lower():
                    return user_id
        return None
    except Exception:
        return None

# Validate and get user_id from username, raising HTTPException if not found
def validate_and_get_user_id(username: str) -> str:
    user_id = get_user_id_by_username(username)
    if not user_id:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    return user_id

# Validate API key from header
def validate_api_key(x_api_key: Optional[str] = Header(None)):
    expected_api_key = os.getenv("API_KEY")
    if not expected_api_key:
        raise HTTPException(status_code=500, detail="API key not configured")

    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")

    if x_api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return True

# Request model for points modification
class PointsRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    points: int = Field(..., ge=-MAX_POINTS, le=MAX_POINTS)

# Response model for points modification
class PointsResponse(BaseModel):
    success: bool
    username: str
    user_id: str
    points_added: int
    new_total: int
    message: str

# Request model for listening time modification
class TimeRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    seconds: int = Field(..., ge=-MAX_SECONDS, le=MAX_SECONDS)

# Response model for listening time modification
class TimeResponse(BaseModel):
    success: bool
    username: str
    user_id: str
    seconds_added: int
    new_total: float
    message: str

# Request model for adding sound data
class AddSoundRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    sound_name: str = Field(..., min_length=1, max_length=128)
    total_time: float = Field(..., ge=0, le=MAX_SECONDS)
    session_count: int = Field(default=1, ge=0, le=1_000_000)

# Response model for adding sound data
class AddSoundResponse(BaseModel):
    success: bool
    username: str
    user_id: str
    sound_name: str
    message: str

# Request model for user deletion
class DeleteUserRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)

# Response model for user deletion
class DeleteUserResponse(BaseModel):
    success: bool
    user_id: str
    message: str

# Request model for server time modification
class ServerTimeRequest(BaseModel):
    guild_id: str = Field(..., min_length=1, max_length=64)
    seconds: int = Field(..., ge=-MAX_SECONDS, le=MAX_SECONDS)

# Response model for server time modification
class ServerTimeResponse(BaseModel):
    success: bool
    guild_id: str
    server_name: str
    seconds_added: int
    new_total: float
    message: str

# Add or remove points from a user by username (protected by API key)
@router.post("/points", response_model=PointsResponse, dependencies=[Depends(validate_api_key)])
async def modify_user_points(request: PointsRequest):
    try:
        # Convert username to user_id
        user_id = validate_and_get_user_id(request.username)

        # Get current user stats
        user_stats = cozy_gamification.get_user_stats(user_id)
        
        # Add points (can be negative to remove)
        cozy_gamification.add_points(user_id, request.points, "Admin adjustment")
        
        # Get updated stats
        updated_stats = cozy_gamification.get_user_stats(user_id)
        new_total = updated_stats.get('total_points', 0)
        
        return PointsResponse(
            success=True,
            username=request.username,
            user_id=user_id,
            points_added=request.points,
            new_total=new_total,
            message=f"Successfully {'added' if request.points >= 0 else 'removed'} {abs(request.points)} points"
        )

    except HTTPException:
        raise
    except Exception:
        logging.exception("admin: error modifying points")
        raise HTTPException(status_code=500, detail="Internal error modifying points")

# Add or remove listening time (in seconds) from a user by username (protected by API key)
@router.post("/time", response_model=TimeResponse, dependencies=[Depends(validate_api_key)])
async def modify_user_time(request: TimeRequest):
    try:
        # Convert username to user_id
        user_id = validate_and_get_user_id(request.username)

        # Get current user stats
        user_stats = cozy_gamification.get_user_stats(user_id)
        if user_stats is None:
            raise HTTPException(status_code=404, detail="User stats not found")
        current_time = user_stats.get('listening_time', 0)
        
        # Add time (can be negative to remove)
        new_time = current_time + request.seconds
        
        # Prevent negative listening time
        if new_time < 0:
            new_time = 0
            seconds_actually_added = -current_time
        else:
            seconds_actually_added = request.seconds
        
        # Update user stats directly
        user_stats['listening_time'] = new_time
        
        # Save the changes
        cozy_gamification.save_user_data()
        
        return TimeResponse(
            success=True,
            username=request.username,
            user_id=user_id,
            seconds_added=seconds_actually_added,
            new_total=new_time,
            message=f"Successfully {'added' if request.seconds >= 0 else 'removed'} {abs(seconds_actually_added)} seconds"
        )

    except HTTPException:
        raise
    except Exception:
        logging.exception("admin: error modifying time")
        raise HTTPException(status_code=500, detail="Internal error modifying time")

# Get raw decrypted user data for debugging (protected by API key)
@router.get("/debug/user/{user_id}")
async def get_raw_user_data(user_id: str, api_key: str = Depends(validate_api_key)):
    try:
        # Get raw user data
        user_stats = cozy_gamification.get_user_stats(user_id)
        if user_stats is None:
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

        return {
            "user_id": user_id,
            "raw_data": user_stats,
            "has_sound_data": "listening_time_by_sound" in user_stats,
            "sound_count": len(user_stats.get("listening_time_by_sound", {})),
            "sounds": list(user_stats.get("listening_time_by_sound", {}).keys()) if "listening_time_by_sound" in user_stats else []
        }

    except HTTPException:
        raise
    except Exception:
        logging.exception("admin: error getting user data")
        raise HTTPException(status_code=500, detail="Internal error getting user data")

# Get all decrypted cozy_points.json data for debugging (protected by API key)
@router.get("/debug/all-data")
async def get_all_raw_data(
    api_key: str = Depends(validate_api_key),
    limit: int = Query(default=100, ge=1, le=MAX_DEBUG_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
):
    try:
        # Counts are computed over the full dataset; raw_data is paginated
        # to avoid dumping the entire user_data dict on a single request.
        all_data = cozy_gamification.user_data

        users_without_sounds = 0
        users_with_sounds = 0
        for user_id, user_stats in all_data.items():
            if "listening_time_by_sound" not in user_stats or len(user_stats.get("listening_time_by_sound", {})) == 0:
                users_without_sounds += 1
            else:
                users_with_sounds += 1

        items = list(all_data.items())
        page = dict(items[offset:offset + limit])

        return {
            "total_users": len(all_data),
            "users_with_sound_data": users_with_sounds,
            "users_without_sound_data": users_without_sounds,
            "offset": offset,
            "limit": limit,
            "returned": len(page),
            "raw_data": page,
        }

    except HTTPException:
        raise
    except Exception:
        logging.exception("admin: error getting all data")
        raise HTTPException(status_code=500, detail="Internal error getting all data")

# Add listening_time_by_sound data to a user by username (protected by API key)
@router.post("/add-sound", response_model=AddSoundResponse, dependencies=[Depends(validate_api_key)])
async def add_user_sound(request: AddSoundRequest):
    try:
        # Convert username to user_id
        user_id = validate_and_get_user_id(request.username)

        # Get user stats
        user_stats = cozy_gamification.get_user_stats(user_id)
        if user_stats is None:
            raise HTTPException(status_code=404, detail="User stats not found")

        # Initialize listening_time_by_sound if not exists
        if "listening_time_by_sound" not in user_stats:
            user_stats["listening_time_by_sound"] = {}
        
        # Add or update sound data
        user_stats["listening_time_by_sound"][request.sound_name] = {
            "total_time": request.total_time,
            "session_count": request.session_count,
            "consecutive_time": 0.0
        }
        
        # Save the changes
        cozy_gamification.save_user_data()
        
        return AddSoundResponse(
            success=True,
            username=request.username,
            user_id=user_id,
            sound_name=request.sound_name,
            message=f"Successfully added {request.sound_name} with {request.total_time}s total time"
        )

    except HTTPException:
        raise
    except Exception:
        logging.exception("admin: error adding sound data")
        raise HTTPException(status_code=500, detail="Internal error adding sound data")

# Delete a user completely from the database by user_id (protected by API key)
@router.delete("/user", response_model=DeleteUserResponse, dependencies=[Depends(validate_api_key)])
async def delete_user(request: DeleteUserRequest):
    try:
        user_id = request.user_id
        
        # Check if user exists in user_data
        if user_id not in cozy_gamification.user_data:
            raise HTTPException(status_code=404, detail=f"User with ID '{user_id}' not found")
        
        # Delete user from cozy_points data
        del cozy_gamification.user_data[user_id]
        
        # Delete user from usernames cache
        if user_id in cozy_gamification.usernames:
            del cozy_gamification.usernames[user_id]
        
        # Save both files
        cozy_gamification.save_user_data()
        cozy_gamification.save_usernames()
        
        return DeleteUserResponse(
            success=True,
            user_id=user_id,
            message=f"Successfully deleted user '{user_id}' and all associated data"
        )

    except HTTPException:
        raise
    except Exception:
        logging.exception("admin: error deleting user")
        raise HTTPException(status_code=500, detail="Internal error deleting user")

# Add or remove listening time (in seconds) from a server by guild_id (protected by API key)
@router.post("/server-time", response_model=ServerTimeResponse, dependencies=[Depends(validate_api_key)])
async def modify_server_time(request: ServerTimeRequest):
    try:
        guild_id = str(request.guild_id)

        # Load server voice time data
        voice_time_data = load_voice_time_data()

        # Check if server exists in data
        if guild_id not in voice_time_data:
            # Initialize new server with 0 time
            voice_time_data[guild_id] = [None, 0]

        # Get current server data
        guild_data = voice_time_data[guild_id]

        # Extract accumulated time (format: [start_time or None, accumulated_seconds])
        if isinstance(guild_data, list) and len(guild_data) >= 2:
            current_time = guild_data[1]
        else:
            current_time = 0

        # Add time (can be negative to remove)
        new_time = current_time + request.seconds

        # Prevent negative time
        if new_time < 0:
            new_time = 0
            seconds_actually_added = -current_time
        else:
            seconds_actually_added = request.seconds

        # Update server data (preserve start_time if exists)
        start_time = guild_data[0] if isinstance(guild_data, list) and len(guild_data) >= 1 else None
        voice_time_data[guild_id] = [start_time, new_time]

        # Save the changes
        if not save_voice_time_data(voice_time_data):
            raise HTTPException(status_code=500, detail="Failed to save voice time data")

        # Get server name
        server_name = get_server_name_by_id(guild_id)

        return ServerTimeResponse(
            success=True,
            guild_id=guild_id,
            server_name=server_name,
            seconds_added=seconds_actually_added,
            new_total=new_time,
            message=f"Successfully {'added' if request.seconds >= 0 else 'removed'} {abs(seconds_actually_added)} seconds to {server_name}"
        )

    except HTTPException:
        raise
    except Exception:
        logging.exception("admin: error modifying server time")
        raise HTTPException(status_code=500, detail="Internal error modifying server time")
