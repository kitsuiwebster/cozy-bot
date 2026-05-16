from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import json
import os
import logging
from pydantic import BaseModel

# Cap user-supplied list sizes to prevent unbounded responses
MAX_TOP_LIMIT = 1000

# Initialize FastAPI router for server stats endpoints
router = APIRouter()

# Response model for individual server statistics
class ServerStats(BaseModel):
    server_id: str
    server_name: Optional[str] = None
    total_time_seconds: int
    formatted_time: str
    rank: int

# Response model for top servers list
class TopServersResponse(BaseModel):
    servers: List[ServerStats]
    total_count: int

# Load voice channel usage statistics from CouchDB
def load_voice_time_data():
    try:
        from utils.storage.couchdb_client import get_couchdb_client
        db = get_couchdb_client()
        return db.load_voice_time_data()
    except Exception:
        return {}

# Load server names cache from CouchDB
def load_servernames_data():
    try:
        from utils.storage.couchdb_client import get_couchdb_client
        db = get_couchdb_client()
        return db.load_servernames()
    except Exception:
        return {}

# Convert seconds to human-readable duration format
def format_time(total_seconds: int) -> str:
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"

# Get top servers by voice time
@router.get("/top-servers", response_model=TopServersResponse)
async def get_top_servers(limit: Optional[int] = Query(default=None, ge=1, le=MAX_TOP_LIMIT)):
    try:
        # Load voice time and server names data
        guild_voice_time = load_voice_time_data()
        servernames_data = load_servernames_data()
        
        if not guild_voice_time:
            return TopServersResponse(servers=[], total_count=0)
        
        # Sort guilds by accumulated voice time in descending order (with safe access)
        def safe_sort_key(item):
            _, voice_time = item
            if isinstance(voice_time, (list, tuple)) and len(voice_time) > 1:
                return voice_time[1] if isinstance(voice_time[1], (int, float)) else 0
            return 0
        
        sorted_guilds = sorted(guild_voice_time.items(), key=safe_sort_key, reverse=True)
        
        # Limit results if specified
        if limit:
            sorted_guilds = sorted_guilds[:limit]
        
        # Format response
        servers = []
        for index, (guild_id, voice_time) in enumerate(sorted_guilds, start=1):
            # Safe access to voice_time data
            if isinstance(voice_time, (list, tuple)) and len(voice_time) > 1:
                total_seconds = int(voice_time[1]) if isinstance(voice_time[1], (int, float)) else 0
            else:
                total_seconds = 0
            
            # Get cached server name or fallback to Old Server
            server_info = servernames_data.get(guild_id)
            if isinstance(server_info, dict):
                server_name = server_info.get('name', "Old Server")
            else:
                server_name = "Old Server"
            
            server_stats = ServerStats(
                server_id=guild_id,
                server_name=server_name,
                total_time_seconds=total_seconds,
                formatted_time=format_time(total_seconds),
                rank=index
            )
            servers.append(server_stats)
        
        return TopServersResponse(
            servers=servers,
            total_count=len(servers)
        )

    except HTTPException:
        raise
    except Exception:
        logging.exception("top_servers: error fetching top servers")
        raise HTTPException(status_code=500, detail="Internal error fetching top servers")
