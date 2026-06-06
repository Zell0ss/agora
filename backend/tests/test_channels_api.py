from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


MOCK_CHANNEL = {
    "id": 1,
    "title": "Debate SaaS",
    "mode": "debate",
    "incognito": False,
    "created_at": datetime(2026, 6, 6, 10, 0, 0),
    "updated_at": datetime(2026, 6, 6, 10, 0, 0),
}
MOCK_ROSTER_ENTRY = {
    "profile_id": 1,
    "name": "Sócrates",
    "tipo": "tertuliano",
    "speaking_order": 0,
    "active": True,
}


@pytest.mark.asyncio
async def test_create_channel():
    from backend.main import app

    with (
        patch("backend.api.channels.insert_channel", AsyncMock(return_value=1)),
        patch("backend.api.channels.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post("/channels", json={"title": "Debate SaaS"})
    assert resp.status_code == 201
    assert resp.json()["id"] == 1
    assert resp.json()["title"] == "Debate SaaS"


@pytest.mark.asyncio
async def test_list_channels():
    from backend.main import app

    with patch(
        "backend.api.channels.list_channels", AsyncMock(return_value=[MOCK_CHANNEL])
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/channels")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_channel():
    from backend.main import app

    with patch(
        "backend.api.channels.get_channel", AsyncMock(return_value=MOCK_CHANNEL)
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/channels/1")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Debate SaaS"


@pytest.mark.asyncio
async def test_get_channel_not_found():
    from backend.main import app

    with patch("backend.api.channels.get_channel", AsyncMock(return_value=None)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/channels/999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_channel():
    from backend.main import app

    updated = {**MOCK_CHANNEL, "title": "Nuevo título"}
    with (
        patch(
            "backend.api.channels.get_channel",
            AsyncMock(side_effect=[MOCK_CHANNEL, updated]),
        ),
        patch("backend.api.channels.update_channel", AsyncMock()),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.patch("/channels/1", json={"title": "Nuevo título"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Nuevo título"


@pytest.mark.asyncio
async def test_list_roster():
    from backend.main import app

    with (
        patch("backend.api.channels.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch(
            "backend.api.channels.get_full_roster",
            AsyncMock(return_value=[MOCK_ROSTER_ENTRY]),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/channels/1/profiles")
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Sócrates"


@pytest.mark.asyncio
async def test_add_to_roster():
    from backend.main import app

    with (
        patch("backend.api.channels.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch("backend.api.channels.count_active_roster", AsyncMock(return_value=0)),
        patch("backend.api.channels.add_to_roster", AsyncMock()),
        patch(
            "backend.api.channels.get_roster_entry",
            AsyncMock(return_value=MOCK_ROSTER_ENTRY),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/channels/1/profiles", json={"profile_id": 1, "speaking_order": 0}
            )
    assert resp.status_code == 201
    assert resp.json()["profile_id"] == 1
    assert resp.json()["name"] == "Sócrates"


@pytest.mark.asyncio
async def test_add_to_roster_limit_exceeded():
    from backend.main import app

    with (
        patch("backend.api.channels.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch("backend.api.channels.count_active_roster", AsyncMock(return_value=3)),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/channels/1/profiles", json={"profile_id": 4, "speaking_order": 3}
            )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_remove_from_roster():
    from backend.main import app

    with (
        patch("backend.api.channels.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch(
            "backend.api.channels.get_roster_entry",
            AsyncMock(return_value=MOCK_ROSTER_ENTRY),
        ),
        patch("backend.api.channels.remove_from_roster", AsyncMock()),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.delete("/channels/1/profiles/1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_patch_roster_entry():
    from backend.main import app

    updated = {**MOCK_ROSTER_ENTRY, "speaking_order": 1}
    with (
        patch("backend.api.channels.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch(
            "backend.api.channels.get_roster_entry",
            AsyncMock(side_effect=[MOCK_ROSTER_ENTRY, updated]),
        ),
        patch("backend.api.channels.update_roster_entry", AsyncMock()),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.patch("/channels/1/profiles/1", json={"speaking_order": 1})
    assert resp.status_code == 200
    assert resp.json()["speaking_order"] == 1
