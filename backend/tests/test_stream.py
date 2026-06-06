import json

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, AsyncMock


async def _mock_run_turn(channel_id: int, human_content: str):
    yield f"data: {json.dumps({'type': 'start', 'profile_id': 1, 'profile_name': 'Sócrates'}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'token', 'profile_id': 1, 'token': 'Hola'}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'done', 'profile_id': 1, 'profile_name': 'Sócrates', 'tokens_in': 5, 'tokens_out': 3, 'cost_usd': '0.000009'}, ensure_ascii=False)}\n\n"
    yield "data: [TURN_COMPLETE]\n\n"


MOCK_CHANNEL = {"id": 1, "title": "Test", "mode": "debate", "incognito": False}


@pytest.mark.asyncio
async def test_post_message_streams_sse():
    from backend.main import app

    with (
        patch("backend.api.stream.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch("backend.api.stream.run_turn", _mock_run_turn),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            async with ac.stream(
                "POST", "/channels/1/messages", json={"content": "¿SaaS?"}
            ) as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers["content-type"]
                body = ""
                async for chunk in resp.aiter_text():
                    body += chunk

    assert "Sócrates" in body
    assert "Hola" in body
    assert "TURN_COMPLETE" in body


@pytest.mark.asyncio
async def test_post_message_404_unknown_channel():
    from backend.main import app

    with patch("backend.api.stream.get_channel", AsyncMock(return_value=None)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post("/channels/999/messages", json={"content": "hola"})
    assert resp.status_code == 404
