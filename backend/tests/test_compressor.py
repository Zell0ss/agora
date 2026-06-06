import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_maybe_compress_skips_when_below_threshold():
    from backend.services.compressor import maybe_compress

    with (
        patch(
            "backend.services.compressor.get_latest_summary",
            AsyncMock(return_value=None),
        ),
        patch(
            "backend.services.compressor.count_messages_after",
            AsyncMock(return_value=5),
        ),
        patch("backend.services.compressor.get_messages_chunk") as mock_chunk,
        patch("backend.services.compressor.insert_summary") as mock_insert,
    ):
        await maybe_compress(1)
        mock_chunk.assert_not_called()
        mock_insert.assert_not_called()


@pytest.mark.asyncio
async def test_maybe_compress_compresses_when_at_threshold():
    from backend.services.compressor import maybe_compress

    mock_chunk = [
        {"id": 1, "role": "human", "profile_name": None, "content": "Hola"},
        {
            "id": 2,
            "role": "persona",
            "profile_name": "Sócrates",
            "content": "Buena pregunta.",
        },
    ]

    with (
        patch(
            "backend.services.compressor.get_latest_summary",
            AsyncMock(return_value=None),
        ),
        patch(
            "backend.services.compressor.count_messages_after",
            AsyncMock(return_value=30),
        ),
        patch(
            "backend.services.compressor.get_messages_chunk",
            AsyncMock(return_value=mock_chunk),
        ),
        patch(
            "backend.services.compressor._summarize",
            AsyncMock(return_value="Resumen del debate."),
        ),
        patch(
            "backend.services.compressor.insert_summary",
            AsyncMock(return_value=1),
        ) as mock_insert,
    ):
        await maybe_compress(1)
        mock_insert.assert_called_once_with(
            1, "Resumen del debate.", covers_up_to_msg_id=2
        )


@pytest.mark.asyncio
async def test_maybe_compress_uses_summary_after_id():
    from backend.services.compressor import maybe_compress

    mock_summary = {"id": 1, "covers_up_to_msg_id": 50, "content": "Prev summary"}

    with (
        patch(
            "backend.services.compressor.get_latest_summary",
            AsyncMock(return_value=mock_summary),
        ),
        patch(
            "backend.services.compressor.count_messages_after",
            AsyncMock(return_value=5),
        ) as mock_count,
        patch("backend.services.compressor.insert_summary") as mock_insert,
    ):
        await maybe_compress(1)
        mock_count.assert_called_once_with(1, 50)
        mock_insert.assert_not_called()
