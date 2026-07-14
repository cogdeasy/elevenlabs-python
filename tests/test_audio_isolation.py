import pytest
from .utils import DEFAULT_VOICE_FILE, IN_GITHUB

from elevenlabs.client import ElevenLabs
from elevenlabs.play import play

pytestmark = pytest.mark.live_api


def test_audio_isolation() -> None:
    """Test basic audio isolation."""
    client = ElevenLabs()
    audio_file = open(DEFAULT_VOICE_FILE, "rb")
    try:
        audio_stream = client.audio_isolation.convert(audio=audio_file)
        audio = b"".join(chunk for chunk in audio_stream)
        assert isinstance(audio, bytes), "Combined audio should be bytes"
        if not IN_GITHUB:
            play(audio)
    finally:
        audio_file.close()


def test_audio_isolation_as_stream():
    """Test audio isolation with streaming."""
    client = ElevenLabs()
    audio_file = open(DEFAULT_VOICE_FILE, "rb")
    try:
        audio_stream = client.audio_isolation.stream(audio=audio_file)
        audio = b"".join(chunk for chunk in audio_stream)
        assert isinstance(audio, bytes), "Combined audio should be bytes"
        if not IN_GITHUB:
            play(audio)
    finally:
        audio_file.close()
