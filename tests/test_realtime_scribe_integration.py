"""Integration-style tests for the realtime Scribe (speech-to-text) wrapper.

Runs ScribeRealtime against a local mocked WebSocket server that speaks the
realtime STT protocol — no real API key required.
"""

import asyncio
import base64
import json

import pytest
from websockets.asyncio.server import serve

from elevenlabs.realtime.connection import RealtimeEvents
from elevenlabs.realtime.reconnect import ExponentialBackoff, connect_with_backoff
from elevenlabs.realtime.scribe import AudioFormat, CommitStrategy, ScribeRealtime


class MockScribeServer:
    def __init__(self, handler=None):
        self._custom_handler = handler
        self.received_messages = []
        self.request_headers = {}
        self.request_path = ""
        self._server = None
        self.port = 0

    async def _handler(self, websocket):
        self.request_headers = {k.lower(): v for k, v in websocket.request.headers.items()}
        self.request_path = websocket.request.path
        await websocket.send(json.dumps({"message_type": "session_started", "session_id": "sess-1"}))
        transcript_parts = []
        async for raw in websocket:
            message = json.loads(raw)
            self.received_messages.append(message)
            if message.get("message_type") != "input_audio_chunk":
                continue
            if message.get("audio_base_64"):
                transcript_parts.append("hello")
                await websocket.send(json.dumps({
                    "message_type": "partial_transcript",
                    "transcript": " ".join(transcript_parts),
                }))
            if message.get("commit"):
                await websocket.send(json.dumps({
                    "message_type": "committed_transcript",
                    "transcript": " ".join(transcript_parts),
                }))
                transcript_parts = []

    async def __aenter__(self):
        self._server = await serve(self._custom_handler or self._handler, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._server.close()
        await self._server.wait_closed()


@pytest.mark.asyncio
async def test_scribe_realtime_full_flow_against_mocked_server():
    async with MockScribeServer() as server:
        scribe = ScribeRealtime(api_key="test-key", base_url=f"http://127.0.0.1:{server.port}")
        connection = await scribe.connect({
            "model_id": "scribe_v2_realtime",
            "audio_format": AudioFormat.PCM_16000,
            "sample_rate": 16000,
            "commit_strategy": CommitStrategy.MANUAL,
        })

        partials = []
        connection.on(RealtimeEvents.PARTIAL_TRANSCRIPT, lambda data: partials.append(data))

        async with connection:
            session = await connection.wait_for(RealtimeEvents.SESSION_STARTED, timeout=5)
            assert session["session_id"] == "sess-1"

            chunk = base64.b64encode(b"\x00\x01" * 160).decode()
            await connection.send({"audio_base_64": chunk})
            await connection.commit()

            committed = await connection.wait_for(RealtimeEvents.COMMITTED_TRANSCRIPT, timeout=5)
            assert committed["transcript"] == "hello"

        assert partials and partials[0]["transcript"] == "hello"

        # Server saw auth header and query parameters
        assert server.request_headers.get("xi-api-key") == "test-key"
        assert server.request_path.startswith("/v1/speech-to-text/realtime")
        assert "model_id=scribe_v2_realtime" in server.request_path
        assert "audio_format=pcm_16000" in server.request_path
        assert "commit_strategy=manual" in server.request_path

        # Client sent well-formed audio chunk messages
        audio_messages = [m for m in server.received_messages if m.get("audio_base_64")]
        assert audio_messages and audio_messages[0]["sample_rate"] == 16000
        commit_messages = [m for m in server.received_messages if m.get("commit")]
        assert len(commit_messages) == 1


@pytest.mark.asyncio
async def test_scribe_realtime_error_event_from_server():
    async def error_handler(websocket):
        await websocket.send(json.dumps({"message_type": "quota_exceeded", "detail": "out of quota"}))
        await asyncio.sleep(0.5)

    async with MockScribeServer(handler=error_handler) as server:
        scribe = ScribeRealtime(api_key="test-key", base_url=f"http://127.0.0.1:{server.port}")
        connection = await scribe.connect({
            "model_id": "scribe_v2_realtime",
            "audio_format": AudioFormat.PCM_16000,
            "sample_rate": 16000,
        })
        async with connection:
            error = await connection.wait_for(RealtimeEvents.ERROR, timeout=5)
            assert error["message_type"] == "quota_exceeded"


@pytest.mark.asyncio
async def test_scribe_realtime_transcripts_async_iterator_against_mocked_server():
    async with MockScribeServer() as server:
        scribe = ScribeRealtime(api_key="test-key", base_url=f"http://127.0.0.1:{server.port}")
        connection = await scribe.connect({
            "model_id": "scribe_v2_realtime",
            "audio_format": AudioFormat.PCM_16000,
            "sample_rate": 16000,
            "commit_strategy": CommitStrategy.MANUAL,
        })

        transcripts = []

        async def consume():
            async for payload in connection.transcripts():
                transcripts.append(payload["transcript"])
                await connection.close()

        async def drive():
            chunk = base64.b64encode(b"\x00\x01" * 160).decode()
            await connection.send({"audio_base_64": chunk})
            await connection.commit()

        await asyncio.wait_for(asyncio.gather(consume(), drive()), timeout=10)
        assert transcripts == ["hello"]


@pytest.mark.asyncio
async def test_connect_with_backoff_against_mocked_server():
    async with MockScribeServer() as server:
        scribe = ScribeRealtime(api_key="test-key", base_url=f"http://127.0.0.1:{server.port}")
        connection = await connect_with_backoff(
            scribe,
            {
                "model_id": "scribe_v2_realtime",
                "audio_format": AudioFormat.PCM_16000,
                "sample_rate": 16000,
            },
            max_attempts=3,
            backoff=ExponentialBackoff(initial=0.01),
        )
        async with connection:
            session = await connection.wait_for(RealtimeEvents.SESSION_STARTED, timeout=5)
            assert session["session_id"] == "sess-1"


@pytest.mark.asyncio
async def test_connect_with_backoff_retries_connection_refused():
    async with MockScribeServer() as server:
        free_port = server.port
    # Server context exited: the port is now closed and connections are refused
    scribe = ScribeRealtime(api_key="test-key", base_url=f"http://127.0.0.1:{free_port}")
    retries = []
    with pytest.raises(OSError):
        await connect_with_backoff(
            scribe,
            {
                "model_id": "scribe_v2_realtime",
                "audio_format": AudioFormat.PCM_16000,
                "sample_rate": 16000,
            },
            max_attempts=2,
            backoff=ExponentialBackoff(initial=0.01),
            on_retry=lambda attempt, error, delay: retries.append(attempt),
        )
    assert retries == [1]
