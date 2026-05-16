from fastapi import APIRouter, HTTPException
import logging

# Initialize FastAPI router for audio restore endpoints. This module previously
# also exposed save-state / restore-state / finalize-sessions / restore-sessions
# POST endpoints. Those are deliberately gone: they duplicated the live_api
# routes (live_api/app.py) but ran in the public API process where bot_instance
# is always None, so they could only return "not available" — and worse, kept
# a second bot_instance global that risked drifting out of sync. The canonical
# audio-mutation endpoints live under /api/live/audio/* in the live API.
router = APIRouter()


# Get pending audio restore tasks (read-only against CouchDB — safe in this process)
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
