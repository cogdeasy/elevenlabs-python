"""Typed payloads for events emitted by :class:`RealtimeConnection`.

These are ``TypedDict`` views over the JSON messages sent by the realtime
speech-to-text WebSocket API.  ``total=False`` is used because the server may
omit optional fields; ``message_type`` is present on every server message.
"""

import typing

from typing_extensions import Required


class SessionStartedEvent(typing.TypedDict, total=False):
    """Payload for :attr:`RealtimeEvents.SESSION_STARTED`."""

    message_type: Required[str]
    session_id: str


class PartialTranscriptEvent(typing.TypedDict, total=False):
    """Payload for :attr:`RealtimeEvents.PARTIAL_TRANSCRIPT`."""

    message_type: Required[str]
    transcript: str


class CommittedTranscriptEvent(typing.TypedDict, total=False):
    """Payload for :attr:`RealtimeEvents.COMMITTED_TRANSCRIPT`."""

    message_type: Required[str]
    transcript: str


class TranscriptWord(typing.TypedDict, total=False):
    """A single word with character-level timing information."""

    text: str
    start: float
    end: float


class CommittedTranscriptWithTimestampsEvent(typing.TypedDict, total=False):
    """Payload for :attr:`RealtimeEvents.COMMITTED_TRANSCRIPT_WITH_TIMESTAMPS`."""

    message_type: Required[str]
    transcript: str
    words: typing.List[TranscriptWord]


class RealtimeErrorEvent(typing.TypedDict, total=False):
    """Payload for :attr:`RealtimeEvents.ERROR` and the specific error events.

    ``message_type`` identifies the concrete error (e.g. ``quota_exceeded``,
    ``auth_error``); ``error``/``detail`` carry a human-readable description.
    """

    message_type: str
    error: str
    detail: str


RealtimeEventPayload = typing.Union[
    SessionStartedEvent,
    PartialTranscriptEvent,
    CommittedTranscriptEvent,
    CommittedTranscriptWithTimestampsEvent,
    RealtimeErrorEvent,
    typing.Dict[str, typing.Any],
]


__all__ = [
    "SessionStartedEvent",
    "PartialTranscriptEvent",
    "CommittedTranscriptEvent",
    "TranscriptWord",
    "CommittedTranscriptWithTimestampsEvent",
    "RealtimeErrorEvent",
    "RealtimeEventPayload",
]
