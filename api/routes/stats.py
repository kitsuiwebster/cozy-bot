from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
import os

# Initialize FastAPI router for stats endpoints
router = APIRouter()

# Response model for total stats endpoint
class TotalStats(BaseModel):
    current_listeners: int
    message: str
    servers_with_bot: int
    total_servers: int

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
        if bot_instance is None:
            raise HTTPException(status_code=503, detail="Bot not available")

        # Count only users with active sound sessions (actually listening)
        active_listeners = 0
        servers_with_bot = 0

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

        return TotalStats(
            current_listeners=active_listeners,
            message=get_cozy_message(active_listeners),
            servers_with_bot=servers_with_bot,
            total_servers=len(bot_instance.guilds)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching total stats: {str(e)}")