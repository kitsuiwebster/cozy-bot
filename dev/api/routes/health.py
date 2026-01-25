from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import discord

router = APIRouter()

# Global bot reference that will be set by the main module
bot_instance = None

def set_bot_instance(bot):
    """Set the bot instance for health check access"""
    global bot_instance
    bot_instance = bot

class HealthResponse(BaseModel):
    status: str
    details: dict = {}

class BotHealthResponse(BaseModel):
    status: str
    connected: bool
    guilds: int = 0
    latency_ms: float = 0.0

@router.get("/health", response_model=HealthResponse)
async def api_health():
    """
    API health check endpoint.
    Returns the status of the FastAPI service.
    """
    return {
        "status": "ok",
        "details": {
            "service": "cozybot-api",
            "version": "1.0.22"
        }
    }

@router.get("/bot/health", response_model=BotHealthResponse)
async def bot_health():
    """
    Discord bot health check endpoint.
    Returns the connection status of the Discord bot.
    """
    if bot_instance is None:
        raise HTTPException(
            status_code=503,
            detail="Bot instance not available"
        )

    # Check if bot is connected to Discord gateway
    is_connected = bot_instance.is_ready() and not bot_instance.is_closed()

    if not is_connected:
        raise HTTPException(
            status_code=503,
            detail="Bot is not connected to Discord"
        )

    # Get latency in milliseconds
    latency_ms = round(bot_instance.latency * 1000, 2)

    return {
        "status": "ok",
        "connected": True,
        "guilds": len(bot_instance.guilds),
        "latency_ms": latency_ms
    }
