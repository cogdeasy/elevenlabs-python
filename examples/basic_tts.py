"""Basic text-to-speech: convert a string to an MP3 file.

Usage:
    export ELEVENLABS_API_KEY="sk_..."
    python examples/basic_tts.py [output.mp3]
"""

import os
import sys

from elevenlabs.client import ElevenLabs

VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George
MODEL_ID = "eleven_multilingual_v2"


def main() -> None:
    output_path = sys.argv[1] if len(sys.argv) > 1 else "output.mp3"

    client = ElevenLabs(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        base_url=os.environ.get("ELEVENLABS_BASE_URL"),
    )
    audio = client.text_to_speech.convert(
        voice_id=VOICE_ID,
        model_id=MODEL_ID,
        text="Hello from the ElevenLabs Python SDK!",
        output_format="mp3_44100_128",
    )

    with open(output_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
