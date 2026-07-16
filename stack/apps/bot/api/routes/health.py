from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging
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
    Public API health: process is up AND CouchDB is reachable.
    The public API has no bot in-process; its only hard dependency is the DB.
    Returns 503 if CouchDB cannot be queried.
    """
    db_ok = False
    try:
        from utils.storage.couchdb_client import get_couchdb_client
        db = get_couchdb_client()
        # Cheap probe: ask for a doc that doesn't exist. Returns None gracefully
        # if the connection works; raises if the DB is unreachable / misauthed.
        db.get_document(db.db, "__health_probe__", default=None)
        db_ok = True
    except Exception:
        logging.exception("health: couchdb probe failed")
        db_ok = False

    payload = {
        "status": "ok" if db_ok else "degraded",
        "details": {
            "service": "cozybot-api",
            "version": "2.1.5",
            "couchdb_reachable": db_ok,
        },
    }
    if not db_ok:
        return JSONResponse(content=payload, status_code=503)
    return payload
