"""Shared pytest configuration.

Tests that call the live ElevenLabs API are marked with ``@pytest.mark.live_api``
(usually via a module-level ``pytestmark``).  They are skipped automatically when
no ``ELEVENLABS_API_KEY`` is available (e.g. on forks without the secret), so the
offline unit/integration suite can run anywhere.
"""

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live_api: test calls the live ElevenLabs API and requires ELEVENLABS_API_KEY",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list) -> None:
    if os.environ.get("ELEVENLABS_API_KEY"):
        return
    skip_live = pytest.mark.skip(reason="ELEVENLABS_API_KEY is not set; skipping live API tests")
    for item in items:
        if item.get_closest_marker("live_api") is not None:
            item.add_marker(skip_live)
