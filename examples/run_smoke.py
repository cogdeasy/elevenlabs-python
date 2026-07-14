"""CI smoke tier: run examples end-to-end against a local mock ElevenLabs API.

Starts an in-process HTTP server that mimics the handful of REST endpoints the
examples call, then executes each example as a subprocess with
``ELEVENLABS_BASE_URL`` pointing at the mock.  This verifies the examples are
actually runnable (argument parsing, client construction, request/response
handling), not just importable.  No real API key or network access is needed.

Usage:
    python examples/run_smoke.py
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EXAMPLES_DIR = pathlib.Path(__file__).parent


class MockElevenLabsHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_audio(self) -> None:
        body = b"\x00\x01" * 512
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        # Consume the request body so the client isn't left blocked on write
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        path = self.path.split("?")[0]
        if path.startswith("/v1/text-to-speech/"):
            self._send_audio()
        elif path == "/v1/convai/agents/create":
            self._send_json({"agent_id": "agent-mock-1"})
        elif path == "/v1/voices/add":
            self._send_json({"voice_id": "voice-mock-1", "requires_verification": False})
        else:
            self._send_json({"detail": f"unmocked POST {path}"}, status=404)

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path.startswith("/v1/convai/agents/"):
            agent_id = path.rsplit("/", 1)[-1]
            self._send_json(
                {
                    "agent_id": agent_id,
                    "name": "sdk-example-agent",
                    "conversation_config": {},
                    "metadata": {"created_at_unix_secs": 0},
                }
            )
        else:
            self._send_json({"detail": f"unmocked GET {path}"}, status=404)

    def do_DELETE(self) -> None:
        self._send_json({})


def run_example(script: str, args: list, base_url: str) -> bool:
    env = {
        **os.environ,
        "ELEVENLABS_API_KEY": "sk-mock-key-for-smoke-tests",
        "ELEVENLABS_BASE_URL": base_url,
    }
    result = subprocess.run(
        [sys.executable, str(EXAMPLES_DIR / script), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    status = "OK  " if result.returncode == 0 else "FAIL"
    print(f"{status} {script} {' '.join(args)}")
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
    return result.returncode == 0


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockElevenLabsHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with tempfile.TemporaryDirectory() as tmp:
            sample = pathlib.Path(tmp) / "sample.mp3"
            sample.write_bytes(b"\x00\x01" * 256)
            output_mp3 = str(pathlib.Path(tmp) / "output.mp3")

            results = [
                run_example("basic_tts.py", [output_mp3], base_url),
                run_example("convai_agent.py", ["smoke-agent"], base_url),
                run_example("voice_cloning.py", [str(sample)], base_url),
            ]
    finally:
        server.shutdown()

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
