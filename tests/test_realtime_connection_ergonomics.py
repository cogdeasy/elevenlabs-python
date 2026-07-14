"""Unit tests for RealtimeConnection async ergonomics: off(), wait_for(),
async event handlers, and async context manager support."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from elevenlabs.realtime.connection import RealtimeConnection, RealtimeEvents


def make_connection() -> RealtimeConnection:
    return RealtimeConnection(websocket=AsyncMock(), current_sample_rate=16000)


class TestOff:
    def test_off_removes_specific_handler(self):
        connection = make_connection()
        calls = []
        handler = lambda data: calls.append(data)
        connection.on(RealtimeEvents.PARTIAL_TRANSCRIPT, handler)
        connection.off(RealtimeEvents.PARTIAL_TRANSCRIPT, handler)
        connection._emit(RealtimeEvents.PARTIAL_TRANSCRIPT, {"transcript": "x"})
        assert calls == []

    def test_off_without_callback_removes_all_handlers(self):
        connection = make_connection()
        calls = []
        connection.on(RealtimeEvents.ERROR, lambda d: calls.append(1))
        connection.on(RealtimeEvents.ERROR, lambda d: calls.append(2))
        connection.off(RealtimeEvents.ERROR)
        connection._emit(RealtimeEvents.ERROR, {})
        assert calls == []

    def test_off_leaves_other_handlers_registered(self):
        connection = make_connection()
        calls = []
        keep = lambda d: calls.append("keep")
        drop = lambda d: calls.append("drop")
        connection.on(RealtimeEvents.ERROR, keep)
        connection.on(RealtimeEvents.ERROR, drop)
        connection.off(RealtimeEvents.ERROR, drop)
        connection._emit(RealtimeEvents.ERROR, {})
        assert calls == ["keep"]

    def test_off_unknown_event_is_noop(self):
        connection = make_connection()
        connection.off("nonexistent")
        connection.off(RealtimeEvents.ERROR, lambda d: None)


class TestWaitFor:
    async def test_wait_for_resolves_with_event_payload(self):
        connection = make_connection()

        async def emit_later():
            await asyncio.sleep(0.01)
            connection._emit(RealtimeEvents.COMMITTED_TRANSCRIPT, {"transcript": "done"})

        task = asyncio.ensure_future(emit_later())
        data = await connection.wait_for(RealtimeEvents.COMMITTED_TRANSCRIPT, timeout=2)
        await task
        assert data == {"transcript": "done"}

    async def test_wait_for_times_out(self):
        connection = make_connection()
        with pytest.raises(asyncio.TimeoutError):
            await connection.wait_for(RealtimeEvents.COMMITTED_TRANSCRIPT, timeout=0.05)

    async def test_wait_for_cleans_up_handler(self):
        connection = make_connection()

        async def emit_later():
            await asyncio.sleep(0.01)
            connection._emit(RealtimeEvents.SESSION_STARTED, {"session_id": "s"})

        task = asyncio.ensure_future(emit_later())
        await connection.wait_for(RealtimeEvents.SESSION_STARTED, timeout=2)
        await task
        assert RealtimeEvents.SESSION_STARTED not in connection._event_handlers


class TestAsyncHandlers:
    async def test_async_handler_is_awaited(self):
        connection = make_connection()
        calls = []

        async def handler(data):
            calls.append(data)

        connection.on(RealtimeEvents.PARTIAL_TRANSCRIPT, handler)
        connection._emit(RealtimeEvents.PARTIAL_TRANSCRIPT, {"transcript": "hi"})
        await asyncio.sleep(0.05)
        assert calls == [{"transcript": "hi"}]

    async def test_async_handler_exception_does_not_break_emit(self, capsys):
        connection = make_connection()
        calls = []

        async def bad_handler(data):
            raise RuntimeError("boom")

        connection.on(RealtimeEvents.ERROR, bad_handler)
        connection.on(RealtimeEvents.ERROR, lambda d: calls.append(d))
        connection._emit(RealtimeEvents.ERROR, {"error": "e"})
        await asyncio.sleep(0.05)
        assert calls == [{"error": "e"}]
        assert "boom" in capsys.readouterr().out


class TestAsyncContextManager:
    async def test_aexit_closes_connection(self):
        websocket = AsyncMock()
        connection = RealtimeConnection(websocket=websocket, current_sample_rate=16000)
        async with connection as conn:
            assert conn is connection
        websocket.close.assert_awaited_once_with(1000, "User ended conversation")
