"""Shared pytest configuration.

Tests that call the live ElevenLabs API are skipped automatically when no
``ELEVENLABS_API_KEY`` is available (e.g. on forks without the secret), so the
offline unit/integration suite can run anywhere.
"""

import os

import pytest

LIVE_API_TEST_MODULES = {
    "e2e_test_convai",
    "test_audio_isolation",
    "test_history",
    "test_models",
    "test_sts",
    "test_stt",
    "test_tts",
    "test_ttsfx",
    "test_ttv",
    "test_voices",
}


def pytest_collection_modifyitems(config: pytest.Config, items: list) -> None:
    if os.environ.get("ELEVENLABS_API_KEY"):
        return
    skip_live = pytest.mark.skip(reason="ELEVENLABS_API_KEY is not set; skipping live API tests")
    for item in items:
        module_name = item.module.__name__.rsplit(".", 1)[-1]
        if module_name in LIVE_API_TEST_MODULES:
            item.add_marker(skip_live)
