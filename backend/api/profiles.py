from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.db.queries.profiles import (
    archive_profile,
    get_profile,
    insert_profile,
    list_profiles,
    update_profile,
)
from backend.schemas.models import ProfileIn, ProfileOut, ProfilePatch

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=list[ProfileOut])
async def list_profiles_endpoint():
    return await list_profiles()


@router.post("", response_model=ProfileOut, status_code=201)
async def create_profile(body: ProfileIn):
    profile_id = await insert_profile(
        name=body.name,
        tipo=body.tipo,
        model=body.model,
        temperature=body.temperature,
        color=body.color,
        funcion=body.funcion,
        system_prompt=body.system_prompt,
    )
    return await get_profile(profile_id)


@router.get("/{profile_id}", response_model=ProfileOut)
async def get_profile_endpoint(profile_id: int):
    profile = await get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    return profile


@router.patch("/{profile_id}", response_model=ProfileOut)
async def patch_profile(profile_id: int, body: ProfilePatch):
    profile = await get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    fields = body.model_dump(exclude_none=True)
    await update_profile(profile_id, fields)
    return await get_profile(profile_id)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: int):
    profile = await get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    await archive_profile(profile_id)
    return Response(status_code=204)
