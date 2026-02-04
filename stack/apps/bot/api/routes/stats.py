from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
import os
import json
import asyncio
import urllib.request
from utils.storage.couchdb_client import get_couchdb_client

# Initialize FastAPI router for stats endpoints
router = APIRouter()

# Response model for total stats endpoint
class TotalStats(BaseModel):
    current_listeners: int
    message: str
    servers_with_bot: int
    total_servers: int
    listeners_by_sound: dict = {}
    active_usernames: list[str] = []
    last_updated: str | None = None

# Get cozy message based on current listener count
def get_cozy_message(total_people: int) -> str:
    if total_people == 0:
        return "🌙 It's quiet right now... Join a voice channel and invite me for some cozy sounds!"
    elif total_people == 1:
        return "🌧️  1 person is currently enjoying some cozy vibes!"
    elif total_people <= 5:
        return f"✨ {total_people} cozy listeners are currently relaxing together!"
    elif total_people <= 10:
        return f"🎵 {total_people} people are currently in cozy mode! The relaxation is spreading!"
    else:
        return f"🌊 Wow! {total_people} people are currently soaking in coziness! What a peaceful community!"

# Global bot reference that will be set by the main module
bot_instance = None

# Set the bot instance for live access
def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot

# Get current statistics about active CozyBot listeners - LIVE DATA (only counts users with active sounds)
@router.get("/total", response_model=TotalStats)
async def get_total_stats():
    try:
        live_api_url = os.getenv("COZY_LIVE_API_URL", "http://cozy-live-bot:8002")
        live_stats = None

        try:
            def _fetch_live():
                with urllib.request.urlopen(f"{live_api_url}/api/live/bot/stats", timeout=2) as resp:
                    return json.loads(resp.read().decode())

            live_stats = await asyncio.to_thread(_fetch_live)
        except Exception:
            live_stats = None

        total_servers = 0
        servers_with_bot = 0
        active_listeners = 0
        listeners_by_sound = {}
        active_usernames = []
        last_updated = None

        # Try CouchDB for baseline totals (works even when bot is in another process)
        try:
            db = get_couchdb_client()
            servernames = db.load_servernames()
            total_servers = len(servernames)
            if not live_stats:
                live_stats = db.load_live_stats() or {}
        except Exception:
            total_servers = 0
            if not live_stats:
                live_stats = {}

        if live_stats:
            active_listeners = int(live_stats.get('current_listeners', 0) or 0)
            servers_with_bot = int(live_stats.get('servers_with_bot', 0) or 0)
            listeners_by_sound = live_stats.get('listeners_by_sound', {}) or {}
            active_usernames = live_stats.get('active_usernames', []) or []
            last_updated = live_stats.get('last_updated')
            if live_stats.get('total_servers') is not None:
                total_servers = int(live_stats.get('total_servers') or 0)

        # Count only users with active sound sessions (actually listening)
        if bot_instance is not None:
            # Get gamification instance to check active sound sessions
            from cogs.stats.gamification import cozy_gamification

            # Count servers where bot is connected
            for guild in bot_instance.guilds:
                voice_state = guild.voice_client
                if voice_state and voice_state.channel:
                    servers_with_bot += 1

            # Count only users who have an active sound session
            if hasattr(cozy_gamification, 'user_data'):
                for user_id, user_stats in cozy_gamification.user_data.items():
                    current_sound = user_stats.get('current_sound')
                    # Check if user has an active sound session (with start_time)
                    if current_sound and isinstance(current_sound, dict) and 'start_time' in current_sound:
                        active_listeners += 1
                        sound_name = current_sound.get('name')
                        if sound_name:
                            listeners_by_sound[sound_name] = listeners_by_sound.get(sound_name, 0) + 1

        return TotalStats(
            current_listeners=active_listeners,
            message=get_cozy_message(active_listeners),
            servers_with_bot=servers_with_bot,
            total_servers=total_servers,
            listeners_by_sound=listeners_by_sound,
            active_usernames=active_usernames,
            last_updated=last_updated
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching total stats: {str(e)}")
