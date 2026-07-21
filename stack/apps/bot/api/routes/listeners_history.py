from fastapi import APIRouter
from pydantic import BaseModel
import logging

from utils.storage.couchdb_client import get_couchdb_client
from utils.audio import listener_history

router = APIRouter()


class ListenerPoint(BaseModel):
    date: str
    min: int
    max: int
    avg: float


class ListenersHistoryResponse(BaseModel):
    points: list[ListenerPoint]


@router.get("/listeners-history", response_model=ListenersHistoryResponse)
async def listeners_history(days: int = 400):
    """Daily min/max/avg concurrent listeners for the last `days` days."""
    days = max(1, min(days, 800))
    try:
        points = listener_history.load_history(get_couchdb_client(), days=days)
    except Exception as e:
        logging.error(f"❌ Failed to load listener history: {e}")
        points = []
    return ListenersHistoryResponse(points=points)
