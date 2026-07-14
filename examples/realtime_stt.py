"""Realtime speech-to-text (Scribe): stream raw PCM audio and print transcripts.

Expects a raw 16 kHz mono signed 16-bit little-endian PCM file, e.g.:
    ffmpeg -i input.mp3 -f s16le -ar 16000 -ac 1 input.pcm

Usage:
    export ELEVENLABS_API_KEY="sk_..."
    python examples/realtime_stt.py input.pcm
"""

import asyncio
import base64
import os
import sys

from elevenlabs.realtime.connection import RealtimeEvents
from elevenlabs.realtime.scribe import AudioFormat, CommitStrategy, ScribeRealtime

CHUNK_SIZE = 32000  # 1 second of 16 kHz mono s16le audio


async def main() -> None:
    pcm_path = sys.argv[1]

    scribe = ScribeRealtime(api_key=os.environ["ELEVENLABS_API_KEY"])
    connection = await scribe.connect({
        "model_id": "scribe_v2_realtime",
        "audio_format": AudioFormat.PCM_16000,
        "sample_rate": 16000,
        "commit_strategy": CommitStrategy.MANUAL,
    })

    connection.on(
        RealtimeEvents.PARTIAL_TRANSCRIPT,
        lambda data: print(f"[partial] {data.get('transcript', '')}"),
    )

    async with connection:
        await connection.wait_for(RealtimeEvents.SESSION_STARTED, timeout=10)

        with open(pcm_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                await connection.send({"audio_base_64": base64.b64encode(chunk).decode()})

        await connection.commit()
        committed = await connection.wait_for(RealtimeEvents.COMMITTED_TRANSCRIPT, timeout=30)
        print(f"[committed] {committed.get('transcript', '')}")


if __name__ == "__main__":
    asyncio.run(main())
