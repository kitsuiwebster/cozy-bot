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
            "version": "2.0.2"
        }
    }
