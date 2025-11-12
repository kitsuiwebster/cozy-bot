from fastapi import APIRouter, HTTPException
from typing import List, Optional
import json
import os
from pydantic import BaseModel

router = APIRouter()

class ServerStats(BaseModel):
    server_id: str
    server_name: Optional[str] = None
    total_time_seconds: int
    formatted_time: str
    rank: int

class TopServersResponse(BaseModel):
    servers: List[ServerStats]
    total_count: int

def load_voice_time_data():
    """Load voice channel usage statistics from persistent storage"""
    data_file = 'data/voice_time_data.json'
    try:
        with open(data_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def format_time(total_seconds: int) -> str:
    """Convert seconds to human-readable duration format"""
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"

@router.get("/top-servers", response_model=TopServersResponse)
async def get_top_servers(limit: int = 10):
    """Get top servers by voice time"""
    try:
        # Load voice time data
        guild_voice_time = load_voice_time_data()
        
        if not guild_voice_time:
            return TopServersResponse(servers=[], total_count=0)
        
        # Sort guilds by accumulated voice time in descending order
        sorted_guilds = sorted(guild_voice_time.items(), key=lambda x: x[1][1], reverse=True)
        
        # Limit results
        sorted_guilds = sorted_guilds[:limit]
        
        # Format response
        servers = []
        for index, (guild_id, voice_time) in enumerate(sorted_guilds, start=1):
            total_seconds = int(voice_time[1])
            
            server_stats = ServerStats(
                server_id=guild_id,
                server_name=f"Server {guild_id[:8]}",  # Simplified for API, can be enhanced with bot instance
                total_time_seconds=total_seconds,
                formatted_time=format_time(total_seconds),
                rank=index
            )
            servers.append(server_stats)
        
        return TopServersResponse(
            servers=servers,
            total_count=len(servers)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching top servers: {str(e)}")