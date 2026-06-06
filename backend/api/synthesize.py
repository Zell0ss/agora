from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.db.queries.channels import get_channel
from backend.services.synthesizer import run_synthesis

router = APIRouter()


@router.post("/channels/{channel_id}/synthesize")
async def synthesize(channel_id: int) -> StreamingResponse:
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    return StreamingResponse(
        run_synthesis(channel_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
