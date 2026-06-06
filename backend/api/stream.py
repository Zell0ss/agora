from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.db.queries.channels import get_channel
from backend.schemas.models import TurnRequest
from backend.services.orchestrator import run_turn

router = APIRouter()


@router.post("/channels/{channel_id}/messages")
async def post_message(channel_id: int, request: TurnRequest) -> StreamingResponse:
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    return StreamingResponse(
        run_turn(channel_id, request.content),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
