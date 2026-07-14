"""Tests for the hand-written realtime TTS wrapper (realtime_tts.py).

Covers the text_chunker helper and an integration-style test that exercises
convert_realtime() end-to-end against a local mocked WebSocket server —
no real API key required.
"""

import base64
import json
import threading
from unittest.mock import patch

from websockets.sync.client import connect as real_connect
from websockets.sync.server import serve

from elevenlabs.client import ElevenLabs
from elevenlabs.realtime_tts import text_chunker


class TestTextChunker:
    def test_empty_input_yields_nothing(self):
        assert list(text_chunker(iter([]))) == []

    def test_single_chunk_gets_trailing_space(self):
        assert list(text_chunker(iter(["Hello"]))) == ["Hello "]

    def test_splits_after_sentence_punctuation(self):
        chunks = list(text_chunker(iter(["Hello.", "World"])))
        assert chunks == ["Hello. ", "World "]

    def test_leading_splitter_attaches_to_previous_buffer(self):
        chunks = list(text_chunker(iter(["Hello", ", world"])))
        assert chunks == ["Hello, ", " world "]

    def test_no_splitters_buffers_everything(self):
        chunks = list(text_chunker(iter(["ab", "cd", "ef"])))
        assert chunks == ["abcdef "]

    def test_all_output_chunks_end_with_space(self):
        text = ["One.", " Two,", " three!", " Four"]
        for chunk in text_chunker(iter(text)):
            assert chunk.endswith(" ")

    def test_reassembled_text_preserves_content(self):
        text = ["Hello, how are you?", " I am fine.", " Thanks!"]
        joined = "".join(text_chunker(iter(text)))
        assert joined.replace(" ", "") == "".join(text).replace(" ", "")


class TestConvertRealtimeIntegration:
    """convert_realtime() against a local mocked stream-input server."""

    def _run_server(self, received, headers_seen, paths_seen):
        def handler(ws):
            headers_seen.update(dict(ws.request.headers.raw_items())
                                if hasattr(ws.request.headers, "raw_items")
                                else dict(ws.request.headers))
            paths_seen.append(ws.request.path)
            bos = json.loads(ws.recv())
            received.append(bos)
            while True:
                message = json.loads(ws.recv())
                received.append(message)
                if message.get("text") == "":
                    ws.send(json.dumps({"audio": base64.b64encode(b"final-audio").decode(), "isFinal": True}))
                    break
                ws.send(json.dumps({"audio": base64.b64encode(b"chunk-audio").decode()}))
            ws.close(1000)

        server = serve(handler, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.socket.getsockname()[1]
        return server, port

    def test_convert_realtime_streams_audio_from_mocked_server(self):
        received: list = []
        headers_seen: dict = {}
        paths_seen: list = []
        server, port = self._run_server(received, headers_seen, paths_seen)

        # The wrapper always upgrades the base URL to wss://; downgrade to
        # plain ws:// so the client can reach the local mock server.
        def plaintext_connect(uri, **kwargs):
            return real_connect(uri.replace("wss://", "ws://", 1), **kwargs)

        try:
            client = ElevenLabs(api_key="test-key", base_url=f"http://127.0.0.1:{port}")
            with patch("elevenlabs.realtime_tts.connect", side_effect=plaintext_connect):
                audio = b"".join(
                    client.text_to_speech.convert_realtime(
                        voice_id="voice-123",
                        text=iter(["Hello world.", " Goodbye."]),
                        model_id="eleven_turbo_v2",
                    )
                )
        finally:
            server.shutdown()

        assert b"final-audio" in audio

        # BOS message initializes the stream
        assert received[0]["text"] == " "
        assert received[0]["generation_config"] == {"chunk_length_schedule": [50]}
        # EOS message terminates the stream
        assert received[-1]["text"] == ""
        # Text chunks were forwarded in between
        sent_text = "".join(m["text"] for m in received[1:-1])
        assert "Hello world." in sent_text and "Goodbye." in sent_text

        # Auth header and URL routing
        header_items = {k.lower(): v for k, v in headers_seen.items()}
        assert header_items.get("xi-api-key") == "test-key"
        assert paths_seen[0].startswith("/v1/text-to-speech/voice-123/stream-input")
        assert "model_id=eleven_turbo_v2" in paths_seen[0]
