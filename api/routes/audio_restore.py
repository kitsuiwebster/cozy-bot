from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
import os
import logging

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# TEMPORARY FIX: Disable audio_state_manager import until path issues resolved
try:
    # from utils.audio.audio_state_manager import audio_state_manager
    audio_state_manager = None  # Temporarily disabled
    logging.warning("Audio state manager temporarily disabled due to import issues")
except ImportError as e:
    logging.error(f"Failed to import audio_state_manager: {e}")
    audio_state_manager = None

# Global bot reference that will be set by the main module
bot_instance = None

def set_bot_instance(bot):
    """Set the bot instance for API access"""
    global bot_instance
    bot_instance = bot

router = APIRouter()

class AudioStateResponse(BaseModel):
    success: bool
    sessions_saved: int
    message: str

class RestoreStatusResponse(BaseModel):
    success: bool
    sessions_restored: int
    message: str

@router.post("/audio/save-state", response_model=AudioStateResponse)
async def save_audio_state():
    """Save current audio state before deployment"""
    try:
        if not audio_state_manager or not bot_instance:
            raise HTTPException(status_code=503, detail="Audio manager not available")
        
        # Save current audio state
        sessions_saved = audio_state_manager.save_current_state(bot_instance)
        
        return AudioStateResponse(
            success=True,
            sessions_saved=sessions_saved,
            message=f"Saved {sessions_saved} active audio sessions"
        )
        
    except Exception as e:
        logging.error(f"❌ Failed to save audio state: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save audio state: {str(e)}")

@router.post("/audio/restore-state", response_model=RestoreStatusResponse) 
async def restore_audio_state():
    """Restore audio state after deployment (manual trigger)"""
    try:
        if not audio_state_manager or not bot_instance:
            raise HTTPException(status_code=503, detail="Audio manager not available")
        
        # Restore audio state
        sessions_restored = audio_state_manager.restore_audio_state(bot_instance)
        
        return RestoreStatusResponse(
            success=True,
            sessions_restored=sessions_restored,
            message=f"Restored {sessions_restored} audio sessions"
        )
        
    except Exception as e:
        logging.error(f"❌ Failed to restore audio state: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restore audio state: {str(e)}")

@router.get("/audio/restore-tasks")
async def get_restore_tasks():
    """Get pending audio restore tasks"""
    try:
        import glob
        restore_files = glob.glob('data/restore_task_*.json')
        
        tasks = []
        for file_path in restore_files:
            try:
                import json
                with open(file_path, 'r') as f:
                    task_data = json.load(f)
                tasks.append({
                    'file': file_path,
                    'guild_id': task_data.get('guild_id'),
                    'sound_name': task_data.get('sound_name'),
                    'timestamp': task_data.get('timestamp')
                })
            except Exception as e:
                logging.error(f"❌ Failed to read restore task {file_path}: {e}")
                continue
        
        return {
            "success": True,
            "pending_tasks": len(tasks),
            "tasks": tasks
        }
        
    except Exception as e:
        logging.error(f"❌ Failed to get restore tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get restore tasks: {str(e)}")