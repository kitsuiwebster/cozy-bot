from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
import sys
import os
from pydantic import BaseModel

# Add project root to path to import cogs
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cogs.stats.gamification import cozy_gamification

router = APIRouter()

# API Key validation
async def validate_api_key(x_api_key: Optional[str] = Header(None)):
    """Validate API key from header"""
    expected_api_key = os.getenv("API_KEY")
    if not expected_api_key:
        raise HTTPException(status_code=500, detail="API key not configured")
    
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    if x_api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return True

class PointsRequest(BaseModel):
    user_id: str
    points: int
    reason: Optional[str] = "Admin adjustment"

class PointsResponse(BaseModel):
    success: bool
    user_id: str
    points_added: int
    new_total: int
    message: str

class TimeRequest(BaseModel):
    user_id: str
    seconds: int
    reason: Optional[str] = "Admin adjustment"

class TimeResponse(BaseModel):
    success: bool
    user_id: str
    seconds_added: int
    new_total: float
    message: str

@router.post("/points", response_model=PointsResponse, dependencies=[Depends(validate_api_key)])
async def modify_user_points(request: PointsRequest):
    """Add or remove points from a user (protected by API key)"""
    try:
        # Get current user stats
        user_stats = cozy_gamification.get_user_stats(request.user_id)
        current_points = user_stats.get('total_points', 0)
        
        # Add points (can be negative to remove)
        cozy_gamification.add_points(request.user_id, request.points, request.reason)
        
        # Get updated stats
        updated_stats = cozy_gamification.get_user_stats(request.user_id)
        new_total = updated_stats.get('total_points', 0)
        
        return PointsResponse(
            success=True,
            user_id=request.user_id,
            points_added=request.points,
            new_total=new_total,
            message=f"Successfully {'added' if request.points >= 0 else 'removed'} {abs(request.points)} points"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error modifying points: {str(e)}")

@router.post("/time", response_model=TimeResponse, dependencies=[Depends(validate_api_key)])
async def modify_user_time(request: TimeRequest):
    """Add or remove listening time (in seconds) from a user (protected by API key)"""
    try:
        # Get current user stats
        user_stats = cozy_gamification.get_user_stats(request.user_id)
        if user_stats is None:
            raise HTTPException(status_code=500, detail="Failed to get user stats")
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
            user_id=request.user_id,
            seconds_added=seconds_actually_added,
            new_total=new_time,
            message=f"Successfully {'added' if request.seconds >= 0 else 'removed'} {abs(seconds_actually_added)} seconds"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error modifying time: {str(e)}")