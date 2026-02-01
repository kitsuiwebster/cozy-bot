from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import logging
import json
import os

try:
    from utils.audio.audio_state_manager import audio_state_manager
except Exception:
    audio_state_manager = None

bot_instance = None

def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot

app = FastAPI(
    title="CozyBot Bot API",
    description="Bot-only control endpoints (live)",
    version="2.0.0"
)

class BotHealthResponse(BaseModel):
    status: str
    connected: bool
    guilds: int = 0
    latency_ms: float = 0.0

class AudioStateResponse(BaseModel):
    success: bool
    sessions_saved: int
    message: str

class RestoreStatusResponse(BaseModel):
    success: bool
    sessions_restored: int
    message: str

class DeploymentRequest(BaseModel):
    version: str
    delay_seconds: int = 30

@app.get("/health")
async def health_check():
    return {"status": "ok", "mode": "live_api"}

@app.get("/api/live/bot/health", response_model=BotHealthResponse)
async def bot_health():
    if bot_instance is None:
        return {
            "status": "degraded",
            "connected": False,
            "guilds": 0,
            "latency_ms": 0.0
        }

    is_connected = bot_instance.is_ready() and not bot_instance.is_closed()
    if not is_connected:
        return {
            "status": "degraded",
            "connected": False,
            "guilds": len(bot_instance.guilds),
            "latency_ms": 0.0
        }

    latency_ms = round(bot_instance.latency * 1000, 2)
    return {
        "status": "ok",
        "connected": True,
        "guilds": len(bot_instance.guilds),
        "latency_ms": latency_ms
    }

@app.post("/api/live/audio/save-state", response_model=AudioStateResponse)
async def save_audio_state():
    if not audio_state_manager or not bot_instance:
        return AudioStateResponse(
            success=False,
            sessions_saved=0,
            message="Audio manager not available"
        )

    sessions_saved = audio_state_manager.save_current_state(bot_instance)
    return AudioStateResponse(
        success=True,
        sessions_saved=sessions_saved,
        message=f"Saved {sessions_saved} active audio sessions"
    )

@app.post("/api/live/audio/restore-state", response_model=RestoreStatusResponse)
async def restore_audio_state():
    if not audio_state_manager or not bot_instance:
        return RestoreStatusResponse(
            success=False,
            sessions_restored=0,
            message="Audio manager not available"
        )

    sessions_restored = audio_state_manager.restore_audio_state(bot_instance)
    return RestoreStatusResponse(
        success=True,
        sessions_restored=sessions_restored,
        message=f"Restored {sessions_restored} audio sessions"
    )

@app.post("/api/live/audio/finalize-sessions")
async def finalize_all_sessions():
    if not bot_instance:
        return {
            "success": False,
            "sessions_finalized": 0,
            "message": "Bot instance not available"
        }

    import main
    from cogs.stats.gamification import cozy_gamification
    from datetime import datetime as _dt

    finalized_count = 0
    for guild in bot_instance.guilds:
        voice_client = guild.voice_client
        if voice_client and voice_client.channel:
            guild_id = str(guild.id)
            for member in voice_client.channel.members:
                if not member.bot:
                    user_id = str(member.id)
                    cozy_gamification.finalize_current_sound(user_id)

                    if guild_id in main.user_voice_sessions:
                        session = main.user_voice_sessions[guild_id]
                        if user_id in session['users']:
                            user_session = session['users'][user_id]
                            duration = (_dt.now() - user_session['join_time']).total_seconds()
                            user_session['accumulated_time'] += duration
                            cozy_gamification.add_listening_time(user_id, duration)

                    finalized_count += 1

    return {
        "success": True,
        "sessions_finalized": finalized_count,
        "message": f"Finalized {finalized_count} active sessions"
    }

@app.post("/api/live/audio/restore-sessions")
async def restore_user_sessions():
    if not bot_instance:
        return {
            "success": False,
            "sessions_restored": 0,
            "message": "Bot instance not available"
        }

    import main
    from datetime import datetime as _dt
    from cogs.stats.gamification import cozy_gamification

    restored_count = 0
    for guild in bot_instance.guilds:
        voice_client = guild.voice_client
        if voice_client and voice_client.channel:
            guild_id = str(guild.id)
            if guild_id not in main.user_voice_sessions:
                main.user_voice_sessions[guild_id] = {'users': {}}

            for member in voice_client.channel.members:
                if not member.bot:
                    user_id = str(member.id)
                    main.user_voice_sessions[guild_id]['users'][user_id] = {
                        'join_time': _dt.now(),
                        'accumulated_time': 0.0
                    }

                    cozy_gamification.join_session(str(member.id), member.name, force_bonus=True)
                    cozy_gamification.update_username(str(member.id), member.name, member.global_name or member.name)

                    current_sound = None
                    for cog_name in ['RainCog', 'SeaCog', 'SparklesCog', 'BackgroundMusicCog']:
                        cog = bot_instance.get_cog(cog_name)
                        if cog and hasattr(cog, 'guild_states'):
                            guild_state = cog.guild_states.get(guild.id, {})
                            if guild_state.get('current_sound'):
                                current_sound = guild_state.get('current_sound')
                                break
                    if current_sound:
                        cozy_gamification.track_sound_start(str(member.id), current_sound)

                    restored_count += 1

    return {
        "success": True,
        "sessions_restored": restored_count,
        "message": f"Restored {restored_count} user sessions"
    }

@app.post("/api/live/deployment/simple-notify")
async def simple_deployment_notify(request: DeploymentRequest):
    if bot_instance is None:
        return {
            "message": "Bot not available",
            "users_notified": 0,
            "proceed_immediately": True
        }

    total_users = 0
    active_guilds = []

    for guild in bot_instance.guilds:
        voice_client = guild.voice_client
        if voice_client and voice_client.channel:
            human_users = [member for member in voice_client.channel.members if not member.bot]
            if human_users:
                total_users += len(human_users)
                active_guilds.append({
                    'guild_id': str(guild.id),
                    'guild_name': guild.name,
                    'channel_id': str(voice_client.channel.id),
                    'channel_name': voice_client.channel.name,
                    'user_count': len(human_users),
                    'user_ids': [str(user.id) for user in human_users]
                })

    if total_users == 0:
        return {
            "message": "No active users found",
            "users_notified": 0,
            "proceed_immediately": True
        }

    notification_data = {
        "version": request.version,
        "delay_seconds": request.delay_seconds,
        "timestamp": datetime.now().isoformat(),
        "total_users": total_users,
        "active_guilds": active_guilds,
        "status": "pending"
    }

    try:
        from utils.storage.couchdb_client import get_couchdb_client
        db = get_couchdb_client()
        doc = notification_data.copy()
        doc["type"] = "deployment_notification"
        db.save_document(db.db, "deployment_notification", doc)
    except Exception:
        os.makedirs('data', exist_ok=True)
        with open('data/deployment_notification.json', 'w') as f:
            json.dump(notification_data, f, indent=2)

    logging.info(f"📢 Deployment notification created for {total_users} users")
    return {
        "message": "Deployment notification file created",
        "users_found": total_users,
        "active_guilds": len(active_guilds),
        "proceed_immediately": False
    }
