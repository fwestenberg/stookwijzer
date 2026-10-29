"""Tests for the Stookwijzer API."""

import asyncio

from stookwijzer import Stookwijzer

DATA = {
    "features": [
        {"properties": {"advies_0": "1", "wind": "3.4", "wind_bft": "2", "lki": "3"}}
    ]
}


def test_failed_update_clears_advice(monkeypatch) -> None:
    """A failed request must not keep the advice from the previous update."""
    client = Stookwijzer(None, 155000, 463000)
    responses = iter([DATA, None])

    async def fake_get_stookwijzer():
        return next(responses)

    monkeypatch.setattr(client, "async_get_stookwijzer", fake_get_stookwijzer)

    asyncio.run(client.async_update())
    assert client.advice == "code_orange"

    asyncio.run(client.async_update())
    assert client.advice is None
