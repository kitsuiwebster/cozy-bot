from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
import os

router = APIRouter()

class TotalStats(BaseModel):
    current_listeners: int
    message: str
    servers_with_bot: int
    total_servers: int

def get_cozy_message(total_people: int) -> str:
    """Get cozy message based on current listener count"""
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

def set_bot_instance(bot):
    """Set the bot instance for live access"""
    global bot_instance
    bot_instance = bot

@router.get("/total", response_model=TotalStats)
async def get_total_stats():
    """Get current statistics about active CozyBot listeners - LIVE DATA"""
    try:
        if bot_instance is None:
            raise HTTPException(status_code=503, detail="Bot not available")
        
        total_people_with_bot = 0
        servers_with_bot = 0
        
        for guild in bot_instance.guilds:
            voice_state = guild.voice_client
            if voice_state and voice_state.channel:
                servers_with_bot += 1
                for member in voice_state.channel.members:
                    if member != bot_instance.user:
                        total_people_with_bot += 1
        
        return TotalStats(
            current_listeners=total_people_with_bot,
            message=get_cozy_message(total_people_with_bot),
            servers_with_bot=servers_with_bot,
            total_servers=len(bot_instance.guilds)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching total stats: {str(e)}")