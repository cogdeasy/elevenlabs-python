import pytest

from elevenlabs import Model
from elevenlabs.client import ElevenLabs

pytestmark = pytest.mark.live_api


def test_models_get_all():
    client = ElevenLabs()
    models = client.models.list()
    assert len(models) > 0
    assert isinstance(models[0], Model)
