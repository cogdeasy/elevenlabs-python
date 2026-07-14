"""
Real-time speech-to-text WebSocket helpers for ElevenLabs API.

This module provides classes for streaming audio to the ElevenLabs
speech-to-text API and receiving real-time transcription results.
"""

from .connection import RealtimeConnection, RealtimeEvents
from .events import (
    CommittedTranscriptEvent,
    CommittedTranscriptWithTimestampsEvent,
    PartialTranscriptEvent,
    RealtimeErrorEvent,
    RealtimeEventPayload,
    SessionStartedEvent,
    TranscriptWord,
)
from .reconnect import ExponentialBackoff, connect_with_backoff
from .scribe import AudioFormat, CommitStrategy, RealtimeAudioOptions, RealtimeUrlOptions, ScribeRealtime

__all__ = [
    "RealtimeConnection",
    "RealtimeEvents",
    "ScribeRealtime",
    "AudioFormat",
    "CommitStrategy",
    "RealtimeAudioOptions",
    "RealtimeUrlOptions",
    "SessionStartedEvent",
    "PartialTranscriptEvent",
    "CommittedTranscriptEvent",
    "CommittedTranscriptWithTimestampsEvent",
    "TranscriptWord",
    "RealtimeErrorEvent",
    "RealtimeEventPayload",
    "ExponentialBackoff",
    "connect_with_backoff",
]

