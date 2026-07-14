"""Speech Engine + FastAPI: serve a Speech Engine WebSocket endpoint.

The ElevenLabs Speech Engine API connects to this endpoint, streams user
transcripts, and plays back whatever text your handler responds with.

Usage:
    pip install fastapi uvicorn
    export ELEVENLABS_API_KEY="sk_..."
    python examples/speech_engine_fastapi.py
"""

import os

import uvicorn
from fastapi import FastAPI, WebSocket

from elevenlabs.speech_engine import SpeechEngineServer, SpeechEngineSession
from elevenlabs.speech_engine.types import wrap_websocket


async def on_transcript(transcript, session: SpeechEngineSession) -> None:
    last_user_message = transcript[-1].content if transcript else ""
    await session.send_response(f"You said: {last_user_message}")


app = FastAPI()

server = SpeechEngineServer(
    api_key=os.environ.get("ELEVENLABS_API_KEY"),
    debug=True,
    on_transcript=on_transcript,
)


@app.websocket("/speech-engine")
async def speech_engine_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    session = server.handle_connection(wrap_websocket(websocket))
    await session.run()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3001)
