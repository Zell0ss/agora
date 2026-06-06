from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


MOCK_PROFILE = {
    "id": 1,
    "name": "Platón",
    "tipo": "tertuliano",
    "model": "claude-sonnet-4-6",
    "temperature": 0.7,
    "color": "azul",
    "funcion": "Dialoga mediante mitos y alegorías",
    "system_prompt": "Eres Platón.",
    "archived": False,
    "created_at": datetime(2026, 6, 6, 10, 0, 0),
    "updated_at": datetime(2026, 6, 6, 10, 0, 0),
}


@pytest.mark.asyncio
async def test_create_profile():
    from backend.main import app

    with (
        patch("backend.api.profiles.insert_profile", AsyncMock(return_value=1)),
        patch("backend.api.profiles.get_profile", AsyncMock(return_value=MOCK_PROFILE)),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/profiles",
                json={
                    "name": "Platón",
                    "funcion": "Dialoga mediante mitos",
                    "system_prompt": "Eres Platón.",
                },
            )
    assert resp.status_code == 201
    assert resp.json()["id"] == 1
    assert resp.json()["name"] == "Platón"


@pytest.mark.asyncio
async def test_list_profiles():
    from backend.main import app

    with patch(
        "backend.api.profiles.list_profiles", AsyncMock(return_value=[MOCK_PROFILE])
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/profiles")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "Platón"


@pytest.mark.asyncio
async def test_get_profile():
    from backend.main import app

    with patch(
        "backend.api.profiles.get_profile", AsyncMock(return_value=MOCK_PROFILE)
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/profiles/1")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Platón"


@pytest.mark.asyncio
async def test_get_profile_not_found():
    from backend.main import app

    with patch("backend.api.profiles.get_profile", AsyncMock(return_value=None)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/profiles/999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_profile():
    from backend.main import app

    updated = {**MOCK_PROFILE, "color": "rojo"}
    with (
        patch(
            "backend.api.profiles.get_profile",
            AsyncMock(side_effect=[MOCK_PROFILE, updated]),
        ),
        patch("backend.api.profiles.update_profile", AsyncMock()),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.patch("/profiles/1", json={"color": "rojo"})
    assert resp.status_code == 200
    assert resp.json()["color"] == "rojo"


@pytest.mark.asyncio
async def test_delete_profile():
    from backend.main import app

    with (
        patch("backend.api.profiles.get_profile", AsyncMock(return_value=MOCK_PROFILE)),
        patch("backend.api.profiles.archive_profile", AsyncMock()),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.delete("/profiles/1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_profile_not_found():
    from backend.main import app

    with patch("backend.api.profiles.get_profile", AsyncMock(return_value=None)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.delete("/profiles/999")
    assert resp.status_code == 404
