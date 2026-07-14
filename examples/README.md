# ElevenLabs Python SDK Examples

Runnable examples for common SDK workflows. Each example reads the API key
from the `ELEVENLABS_API_KEY` environment variable.

| Example | Description |
| --- | --- |
| [`basic_tts.py`](basic_tts.py) | Convert text to speech and save it as an MP3 file. |
| [`convai_agent.py`](convai_agent.py) | Create, fetch, and delete a conversational AI agent. |
| [`voice_cloning.py`](voice_cloning.py) | Create an instant voice clone (IVC) from audio samples. |
| [`realtime_stt.py`](realtime_stt.py) | Stream microphone-format PCM audio to realtime Scribe speech-to-text. |
| [`speech_engine_fastapi.py`](speech_engine_fastapi.py) | Serve a Speech Engine WebSocket endpoint from a FastAPI app. |

## Running

```bash
pip install elevenlabs
export ELEVENLABS_API_KEY="sk_..."

python examples/basic_tts.py
python examples/convai_agent.py
python examples/voice_cloning.py sample1.mp3
python examples/realtime_stt.py path/to/audio.pcm   # raw 16 kHz mono s16le PCM
pip install fastapi uvicorn && python examples/speech_engine_fastapi.py
```

All examples are compile- and import-checked in CI, and the HTTP-based
examples are also executed end-to-end against a local mock API server
(`python examples/run_smoke.py`) — see the `examples` job in
`.github/workflows/ci.yml`.
