"""Voice cloning (IVC): create an instant voice clone from audio samples.

Usage:
    export ELEVENLABS_API_KEY="sk_..."
    python examples/voice_cloning.py sample1.mp3 [sample2.mp3 ...]

Set ELEVENLABS_BASE_URL to point the client at a non-production API
(used by the CI smoke tier to run against a local mock server).
"""

import contextlib
import os
import sys

from elevenlabs.client import ElevenLabs


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python examples/voice_cloning.py sample1.mp3 [sample2.mp3 ...]")
        raise SystemExit(2)

    sample_paths = sys.argv[1:]

    client = ElevenLabs(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        base_url=os.environ.get("ELEVENLABS_BASE_URL"),
    )

    with contextlib.ExitStack() as stack:
        files = [stack.enter_context(open(path, "rb")) for path in sample_paths]
        voice = client.voices.ivc.create(
            name="sdk-example-cloned-voice",
            description="Instant voice clone created by the SDK example",
            files=files,
        )

    print(f"Created voice clone: {voice.voice_id}")
    if voice.requires_verification:
        print("Voice requires verification before use.")


if __name__ == "__main__":
    main()
