from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.db.queries.messages import get_channel_messages
from backend.db.queries.channels import (
    add_to_roster,
    count_active_roster,
    get_channel,
    get_full_roster,
    get_roster_entry,
    insert_channel,
    list_channels,
    remove_from_roster,
    update_channel,
    update_roster_entry,
)
from backend.schemas.models import (
    ChannelIn,
    ChannelOut,
    ChannelPatch,
    MessageOut,
    RosterAddIn,
    RosterEntry,
    RosterPatch,
)

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=list[ChannelOut])
async def list_channels_endpoint():
    return await list_channels()


@router.post("", response_model=ChannelOut, status_code=201)
async def create_channel(body: ChannelIn):
    channel_id = await insert_channel(
        title=body.title, mode=body.mode, incognito=body.incognito
    )
    return await get_channel(channel_id)


@router.get("/{channel_id}", response_model=ChannelOut)
async def get_channel_endpoint(channel_id: int):
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    return channel


@router.patch("/{channel_id}", response_model=ChannelOut)
async def patch_channel(channel_id: int, body: ChannelPatch):
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    fields = body.model_dump(exclude_none=True)
    await update_channel(channel_id, fields)
    return await get_channel(channel_id)


@router.get("/{channel_id}/messages", response_model=list[MessageOut])
async def list_channel_messages(channel_id: int):
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    return await get_channel_messages(channel_id)


@router.get("/{channel_id}/profiles", response_model=list[RosterEntry])
async def list_roster(channel_id: int):
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    return await get_full_roster(channel_id)


@router.post("/{channel_id}/profiles", response_model=RosterEntry, status_code=201)
async def add_profile_to_channel(channel_id: int, body: RosterAddIn):
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    active_count = await count_active_roster(channel_id)
    if active_count >= 3:
        raise HTTPException(
            status_code=400, detail="Channel already has 3 active profiles (maximum)"
        )
    await add_to_roster(
        channel_id=channel_id,
        profile_id=body.profile_id,
        speaking_order=body.speaking_order,
    )
    return await get_roster_entry(channel_id, body.profile_id)


@router.delete("/{channel_id}/profiles/{profile_id}", status_code=204)
async def remove_profile_from_channel(channel_id: int, profile_id: int):
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    entry = await get_roster_entry(channel_id, profile_id)
    if not entry:
        raise HTTPException(
            status_code=404, detail=f"Profile {profile_id} not in channel {channel_id}"
        )
    await remove_from_roster(channel_id, profile_id)
    return Response(status_code=204)


@router.patch("/{channel_id}/profiles/{profile_id}", response_model=RosterEntry)
async def patch_roster_entry(channel_id: int, profile_id: int, body: RosterPatch):
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    entry = await get_roster_entry(channel_id, profile_id)
    if not entry:
        raise HTTPException(
            status_code=404, detail=f"Profile {profile_id} not in channel {channel_id}"
        )
    fields = body.model_dump(exclude_none=True)
    await update_roster_entry(channel_id, profile_id, fields)
    return await get_roster_entry(channel_id, profile_id)
