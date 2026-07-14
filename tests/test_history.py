import pytest

from elevenlabs import ElevenLabs, GetSpeechHistoryResponse

pytestmark = pytest.mark.live_api


def test_history():
    client = ElevenLabs()
    page_size = 5
    history = client.history.list(page_size=page_size)
    assert isinstance(history, GetSpeechHistoryResponse)
