from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
import os
import logging

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from utils.audio.audio_state_manager import audio_state_manager
    logging.info("🎮 utils.audio.audio_state_manager loaded successfully")
except ImportError as e:
    logging.error(f"❌ Failed to import audio_state_manager: {e}")
    audio_state_manager = None

# Global bot reference that will be set by the main module
bot_instance = None

# Set the bot instance for API access
def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot

# Initialize FastAPI router for audio restore endpoints
router = APIRouter()

# Response model for audio state save operation
class AudioStateResponse(BaseModel):
    success: bool
    sessions_saved: int
    message: str

# Response model for audio state restore operation
class RestoreStatusResponse(BaseModel):
    success: bool
    sessions_restored: int
    message: str

# Save current audio state before deployment
@router.post("/audio/save-state", response_model=AudioStateResponse)
async def save_audio_state():
    try:
        if not audio_state_manager or not bot_instance:
            return AudioStateResponse(
                success=False,
                sessions_saved=0,
                message="Audio manager not available in API process"
            )
        
        # Save current audio state
        sessions_saved = audio_state_manager.save_current_state(bot_instance)
        
        return AudioStateResponse(
            success=True,
            sessions_saved=sessions_saved,
            message=f"Saved {sessions_saved} active audio sessions"
        )
        
    except Exception:
        logging.exception("audio_restore: failed to save audio state")
        raise HTTPException(status_code=500, detail="Internal error saving audio state")

# Restore audio state after deployment (manual trigger)
@router.post("/audio/restore-state", response_model=RestoreStatusResponse)
async def restore_audio_state():
    try:
        if not audio_state_manager or not bot_instance:
            return RestoreStatusResponse(
                success=False,
                sessions_restored=0,
                message="Audio manager not available in API process"
            )
        
        # Restore audio state
        sessions_restored = audio_state_manager.restore_audio_state(bot_instance)
        
        return RestoreStatusResponse(
            success=True,
            sessions_restored=sessions_restored,
            message=f"Restored {sessions_restored} audio sessions"
        )
        
    except Exception:
        logging.exception("audio_restore: failed to restore audio state")
        raise HTTPException(status_code=500, detail="Internal error restoring audio state")

# Finalize all active user sessions before deployment
@router.post("/audio/finalize-sessions")
async def finalize_all_sessions():
    try:
        if not bot_instance:
            return {
                "success": False,
                "sessions_finalized": 0,
                "message": "Bot instance not available in API process"
            }
        
        # Import voice session tracking from main
        import main
        
        # Get all guilds where bot is connected to voice
        finalized_count = 0
        for guild in bot_instance.guilds:
            voice_client = guild.voice_client
            if voice_client and voice_client.channel:
                guild_id = str(guild.id)
                
                # Get all users in the voice channel (except bot)
                for member in voice_client.channel.members:
                    if not member.bot:
                        user_id = str(member.id)
                        
                        # Import here to avoid circular imports
                        from cogs.stats.gamification import cozy_gamification
                        
                        # Finalize their current sound session
                        cozy_gamification.finalize_current_sound(user_id)
                        
                        # Also finalize their voice session tracking (like user leaving)
                        if guild_id in main.user_voice_sessions:
                            session = main.user_voice_sessions[guild_id]
                            if user_id in session['users']:
                                # Calculate accumulated time like in normal leave
                                from datetime import datetime
                                user_session = session['users'][user_id]
                                duration = (datetime.now() - user_session['join_time']).total_seconds()
                                user_session['accumulated_time'] += duration
                                
                                # Award points for voice time
                                logging.info(f"👉 USER FINALIZED: {member.name} session ended before deployment")
                        
                        finalized_count += 1
                        
        logging.info(f"👉 Finalized {finalized_count} user sessions before deployment")
        
        return {
            "success": True,
            "sessions_finalized": finalized_count,
            "message": f"Finalized {finalized_count} active sessions"
        }
        
    except Exception:
        logging.exception("audio_restore: failed to finalize sessions")
        raise HTTPException(status_code=500, detail="Internal error finalizing sessions")

# Restore user sessions after deployment
@router.post("/audio/restore-sessions")
async def restore_user_sessions():
    try:
        if not bot_instance:
            return {
                "success": False,
                "sessions_restored": 0,
                "message": "Bot instance not available in API process"
            }
        
        # Import voice session tracking from main
        import main
        
        # Get all guilds where bot is connected to voice
        restored_count = 0
        for guild in bot_instance.guilds:
            voice_client = guild.voice_client
            if voice_client and voice_client.channel:
                guild_id = str(guild.id)
                
                # Reinitialize voice session tracking for this guild
                if guild_id not in main.user_voice_sessions:
                    main.user_voice_sessions[guild_id] = {'users': {}}
                
                # Get all users in the voice channel (except bot)
                for member in voice_client.channel.members:
                    if not member.bot:
                        user_id = str(member.id)
                        
                        # Restore voice session tracking
                        from datetime import datetime
                        main.user_voice_sessions[guild_id]['users'][user_id] = {
                            'join_time': datetime.now(),
                            'accumulated_time': 0.0
                        }
                        
                        # Import here to avoid circular imports
                        from cogs.stats.gamification import cozy_gamification
                        
                        # Start new session (like user joining)
                        cozy_gamification.join_session(str(member.id), member.name, force_bonus=True)
                        cozy_gamification.update_username(str(member.id), member.name, member.global_name or member.name)
                        
                        # If there's currently playing audio, start tracking it
                        # Check what sound is playing in this guild
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
                        logging.info(f"👉 USER RESTORED: {member.name} in {voice_client.channel.name} in {guild.name}")
                        
        logging.info(f"👉 Restored {restored_count} user sessions after deployment")
        
        return {
            "success": True,
            "sessions_restored": restored_count,
            "message": f"Restored {restored_count} user sessions"
        }
        
    except Exception:
        logging.exception("audio_restore: failed to restore sessions")
        raise HTTPException(status_code=500, detail="Internal error restoring sessions")

# Get pending audio restore tasks
@router.get("/audio/restore-tasks")
async def get_restore_tasks():
    try:
        from utils.storage.couchdb_client import get_couchdb_client
        db = get_couchdb_client()

        all_tasks = db.get_all_restore_tasks()

        tasks = []
        for task_id, task_data in all_tasks.items():
            tasks.append({
                'task_id': task_id,
                'guild_id': task_data.get('guild_id'),
                'sound_name': task_data.get('sound_name'),
                'timestamp': task_data.get('timestamp')
            })

        return {
            "success": True,
            "pending_tasks": len(tasks),
            "tasks": tasks
        }

    except Exception:
        logging.exception("audio_restore: failed to get restore tasks")
        raise HTTPException(status_code=500, detail="Internal error getting restore tasks")
