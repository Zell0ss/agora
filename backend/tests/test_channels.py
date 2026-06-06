from unittest.mock import AsyncMock, patch
import pytest


@pytest.mark.asyncio
async def test_list_channel_messages_returns_history():
    from backend.api.channels import router  # noqa: F401 — ensures route registered
    from fastapi.testclient import TestClient
    from backend.main import app

    mock_msgs = [
        {
            "id": 1,
            "role": "human",
            "profile_id": None,
            "content": "Hola",
            "cost_usd": None,
            "created_at": "2026-01-01T10:00:00",
        },
        {
            "id": 2,
            "role": "persona",
            "profile_id": 1,
            "content": "Buenos días",
            "cost_usd": 0.0001,
            "created_at": "2026-01-01T10:00:05",
        },
    ]
    with (
        patch("backend.api.channels.get_channel", AsyncMock(return_value={"id": 1})),
        patch(
            "backend.api.channels.get_channel_messages",
            AsyncMock(return_value=mock_msgs),
        ),
    ):
        client = TestClient(app)
        resp = client.get("/channels/1/messages")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["role"] == "human"
    assert data[1]["profile_id"] == 1


@pytest.mark.asyncio
async def test_list_channel_messages_404_unknown_channel():
    from fastapi.testclient import TestClient
    from backend.main import app

    with patch("backend.api.channels.get_channel", AsyncMock(return_value=None)):
        client = TestClient(app)
        resp = client.get("/channels/99/messages")
    assert resp.status_code == 404
