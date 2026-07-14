"""Unit tests for realtime async ergonomics: typed events, async iterators,
and reconnection/backoff helpers.  No network access required."""

import asyncio
import typing

import pytest

from elevenlabs.realtime import (
    CommittedTranscriptEvent,
    ExponentialBackoff,
    PartialTranscriptEvent,
    RealtimeConnection,
    RealtimeEvents,
    connect_with_backoff,
)


class _DummyWebsocket:
    async def send(self, message: str) -> None:
        pass

    async def close(self, code: int, reason: str) -> None:
        pass


def _make_connection() -> RealtimeConnection:
    return RealtimeConnection(
        websocket=typing.cast(typing.Any, _DummyWebsocket()),
        current_sample_rate=16000,
    )


async def test_events_iterator_yields_until_close():
    connection = _make_connection()

    async def emit_events():
        await asyncio.sleep(0)
        connection._emit(RealtimeEvents.SESSION_STARTED, {"message_type": "session_started", "session_id": "s1"})
        connection._emit(RealtimeEvents.PARTIAL_TRANSCRIPT, {"message_type": "partial_transcript", "transcript": "he"})
        connection._emit(
            RealtimeEvents.COMMITTED_TRANSCRIPT, {"message_type": "committed_transcript", "transcript": "hello"}
        )
        connection._emit(RealtimeEvents.CLOSE)

    seen = []

    async def consume():
        async for event, payload in connection.events():
            seen.append((event, payload))

    await asyncio.gather(consume(), emit_events())

    assert [e for e, _ in seen] == [
        RealtimeEvents.SESSION_STARTED,
        RealtimeEvents.PARTIAL_TRANSCRIPT,
        RealtimeEvents.COMMITTED_TRANSCRIPT,
    ]
    assert seen[2][1]["transcript"] == "hello"


async def test_events_iterator_filters_requested_events():
    connection = _make_connection()

    async def emit_events():
        await asyncio.sleep(0)
        connection._emit(RealtimeEvents.PARTIAL_TRANSCRIPT, {"transcript": "he"})
        connection._emit(RealtimeEvents.COMMITTED_TRANSCRIPT, {"transcript": "hello"})
        connection._emit(RealtimeEvents.CLOSE)

    seen = []

    async def consume():
        async for event, payload in connection.events([RealtimeEvents.COMMITTED_TRANSCRIPT]):
            seen.append((event, payload))

    await asyncio.gather(consume(), emit_events())
    assert seen == [(RealtimeEvents.COMMITTED_TRANSCRIPT, {"transcript": "hello"})]


async def test_transcripts_iterator_committed_only_and_with_partials():
    for include_partial, expected in [(False, ["hello"]), (True, ["he", "hello"])]:
        connection = _make_connection()

        async def emit_events(conn=connection):
            await asyncio.sleep(0)
            conn._emit(RealtimeEvents.PARTIAL_TRANSCRIPT, {"transcript": "he"})
            conn._emit(RealtimeEvents.COMMITTED_TRANSCRIPT, {"transcript": "hello"})
            conn._emit(RealtimeEvents.CLOSE)

        transcripts = []

        async def consume(conn=connection, flag=include_partial):
            async for payload in conn.transcripts(include_partial=flag):
                transcripts.append(payload["transcript"])

        await asyncio.gather(consume(), emit_events())
        assert transcripts == expected


async def test_aiter_protocol_is_events_iterator():
    connection = _make_connection()

    async def emit_events():
        await asyncio.sleep(0)
        connection._emit(RealtimeEvents.SESSION_STARTED, {"session_id": "s1"})
        connection._emit(RealtimeEvents.CLOSE)

    seen = []

    async def consume():
        async for event, _ in connection:
            seen.append(event)

    await asyncio.gather(consume(), emit_events())
    assert seen == [RealtimeEvents.SESSION_STARTED]


async def test_events_queue_cleanup_after_iteration():
    connection = _make_connection()

    async def emit_events():
        await asyncio.sleep(0)
        connection._emit(RealtimeEvents.CLOSE)

    async def consume():
        async for _ in connection.events():
            pass

    await asyncio.gather(consume(), emit_events())
    assert connection._event_queues == []


def test_typed_event_payloads_are_constructible():
    partial: PartialTranscriptEvent = {"message_type": "partial_transcript", "transcript": "he"}
    committed: CommittedTranscriptEvent = {"message_type": "committed_transcript", "transcript": "hello"}
    assert partial["transcript"] == "he"
    assert committed["message_type"] == "committed_transcript"


def test_exponential_backoff_progression_and_cap():
    backoff = ExponentialBackoff(initial=1.0, multiplier=2.0, maximum=5.0)
    assert [backoff.next_delay() for _ in range(4)] == [1.0, 2.0, 4.0, 5.0]
    assert backoff.attempt == 4
    backoff.reset()
    assert backoff.next_delay() == 1.0


def test_exponential_backoff_jitter_bounds():
    backoff = ExponentialBackoff(initial=1.0, multiplier=1.0, jitter=0.5)
    for _ in range(50):
        assert 0.5 <= backoff.next_delay() <= 1.5


def test_exponential_backoff_validation():
    with pytest.raises(ValueError):
        ExponentialBackoff(initial=0)
    with pytest.raises(ValueError):
        ExponentialBackoff(multiplier=0.5)
    with pytest.raises(ValueError):
        ExponentialBackoff(jitter=1.5)


class _FlakyScribe:
    def __init__(self, failures: int, error: Exception):
        self.failures = failures
        self.error = error
        self.attempts = 0

    async def connect(self, options):
        self.attempts += 1
        if self.attempts <= self.failures:
            raise self.error
        return typing.cast(RealtimeConnection, object())


async def test_connect_with_backoff_retries_then_succeeds():
    scribe = _FlakyScribe(failures=2, error=ConnectionError("refused"))
    retries = []
    connection = await connect_with_backoff(
        typing.cast(typing.Any, scribe),
        {"model_id": "m", "audio_format": "pcm_16000", "sample_rate": 16000},
        max_attempts=5,
        backoff=ExponentialBackoff(initial=0.001),
        on_retry=lambda attempt, error, delay: retries.append((attempt, delay)),
    )
    assert connection is not None
    assert scribe.attempts == 3
    assert [attempt for attempt, _ in retries] == [1, 2]


async def test_connect_with_backoff_raises_after_max_attempts():
    scribe = _FlakyScribe(failures=10, error=ConnectionError("refused"))
    with pytest.raises(ConnectionError):
        await connect_with_backoff(
            typing.cast(typing.Any, scribe),
            {"model_id": "m", "audio_format": "pcm_16000", "sample_rate": 16000},
            max_attempts=3,
            backoff=ExponentialBackoff(initial=0.001),
        )
    assert scribe.attempts == 3


async def test_connect_with_backoff_does_not_retry_invalid_options():
    scribe = _FlakyScribe(failures=10, error=ValueError("model_id is required"))
    with pytest.raises(ValueError):
        await connect_with_backoff(
            typing.cast(typing.Any, scribe),
            {"model_id": "m", "audio_format": "pcm_16000", "sample_rate": 16000},
            max_attempts=5,
            backoff=ExponentialBackoff(initial=0.001),
        )
    assert scribe.attempts == 1


async def test_connect_with_backoff_validates_max_attempts():
    scribe = _FlakyScribe(failures=0, error=ConnectionError("refused"))
    with pytest.raises(ValueError):
        await connect_with_backoff(
            typing.cast(typing.Any, scribe),
            {"model_id": "m", "audio_format": "pcm_16000", "sample_rate": 16000},
            max_attempts=0,
        )


async def test_events_iterator_ends_immediately_if_already_closed():
    connection = _make_connection()
    connection._emit(RealtimeEvents.CLOSE)

    seen = []
    async for event, _ in connection.events():
        seen.append(event)
    assert seen == []
