from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TurnRequest(BaseModel):
    content: str


# --- Profiles ---


class ProfileIn(BaseModel):
    name: str
    tipo: Literal["tertuliano", "facilitador"] = "tertuliano"
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.7
    color: str | None = None
    funcion: str
    system_prompt: str


class ProfileOut(BaseModel):
    id: int
    name: str
    tipo: str
    model: str
    temperature: float
    color: str | None
    funcion: str
    system_prompt: str
    archived: bool
    created_at: datetime
    updated_at: datetime


class ProfilePatch(BaseModel):
    name: str | None = None
    model: str | None = None
    temperature: float | None = None
    color: str | None = None
    funcion: str | None = None
    system_prompt: str | None = None


# --- Channels ---


class ChannelIn(BaseModel):
    title: str
    mode: Literal["debate", "critica"] = "debate"
    incognito: bool = False


class ChannelOut(BaseModel):
    id: int
    title: str
    mode: str
    incognito: bool
    created_at: datetime
    updated_at: datetime


class ChannelPatch(BaseModel):
    title: str | None = None
    mode: Literal["debate", "critica"] | None = None
    incognito: bool | None = None


# --- Roster ---


class RosterAddIn(BaseModel):
    profile_id: int
    speaking_order: int = 0


class RosterPatch(BaseModel):
    speaking_order: int | None = None
    active: bool | None = None


class RosterEntry(BaseModel):
    profile_id: int
    name: str
    tipo: str
    speaking_order: int
    active: bool
