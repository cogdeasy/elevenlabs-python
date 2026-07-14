import asyncio
import json
import subprocess
import typing
from enum import Enum

from .events import CommittedTranscriptEvent, RealtimeEventPayload

if typing.TYPE_CHECKING:
    from websockets.asyncio.client import ClientConnection


def _event_key(event: str) -> str:
    return event.value if isinstance(event, Enum) else str(event)


class RealtimeEvents(str, Enum):
    """Events emitted by the RealtimeConnection"""
    OPEN = "open"
    CLOSE = "close"
    SESSION_STARTED = "session_started"
    PARTIAL_TRANSCRIPT = "partial_transcript"
    COMMITTED_TRANSCRIPT = "committed_transcript"
    COMMITTED_TRANSCRIPT_WITH_TIMESTAMPS = "committed_transcript_with_timestamps"
    ERROR = "error"
    AUTH_ERROR = "auth_error"
    QUOTA_EXCEEDED = "quota_exceeded"
    COMMIT_THROTTLED = "commit_throttled"
    TRANSCRIBER_ERROR = "transcriber_error"
    UNACCEPTED_TERMS_ERROR = "unaccepted_terms_error"
    RATE_LIMITED = "rate_limited"
    INPUT_ERROR = "input_error"
    QUEUE_OVERFLOW = "queue_overflow"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    SESSION_TIME_LIMIT_EXCEEDED = "session_time_limit_exceeded"
    CHUNK_SIZE_EXCEEDED = "chunk_size_exceeded"
    INSUFFICIENT_AUDIO_ACTIVITY = "insufficient_audio_activity"



class RealtimeConnection:
    """
    A WebSocket connection for real-time speech-to-text transcription.

    This class handles bidirectional WebSocket communication with the ElevenLabs
    speech-to-text API, managing audio streaming and receiving transcription results.

    Example:
        ```python
        connection = await client.speech_to_text.realtime.connect({
            "audio_format": AudioFormat.PCM_16000,
            "sample_rate": 16000
        })

        connection.on(RealtimeEvents.PARTIAL_TRANSCRIPT, lambda data: print(data))
        connection.on(RealtimeEvents.COMMITTED_TRANSCRIPT, lambda data: print(data))

        # Send audio
        connection.send({"audioBase64": audio_chunk})

        # When done
        connection.commit()
        await connection.close()
        ```
    """

    def __init__(self, websocket: "ClientConnection", current_sample_rate: int, ffmpeg_process: typing.Optional[subprocess.Popen] = None):
        self.websocket = websocket
        self.current_sample_rate = current_sample_rate
        self.ffmpeg_process = ffmpeg_process
        self._event_handlers: typing.Dict[str, typing.List[typing.Callable]] = {}
        self._message_task: typing.Optional[asyncio.Task] = None
        self._callback_tasks: typing.Set[asyncio.Task] = set()
        self._event_queues: typing.List["asyncio.Queue[typing.Tuple[str, typing.Any]]"] = []

    async def __aenter__(self) -> "RealtimeConnection":
        return self

    async def __aexit__(self, exc_type: typing.Any, exc: typing.Any, tb: typing.Any) -> None:
        await self.close()

    def on(self, event: str, callback: typing.Callable) -> None:
        """
        Register an event handler for a specific event type.

        Args:
            event: The event type to listen for (from RealtimeEvents enum)
            callback: The function to call when the event occurs

        Example:
            ```python
            def handle_transcript(data):
                print(f"Transcript: {data['transcript']}")

            connection.on(RealtimeEvents.PARTIAL_TRANSCRIPT, handle_transcript)
            ```
        """
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(callback)

    def off(self, event: str, callback: typing.Optional[typing.Callable] = None) -> None:
        """
        Remove an event handler previously registered with :meth:`on`.

        Args:
            event: The event type the handler was registered for
            callback: The handler to remove. If ``None``, all handlers for
                the event are removed.
        """
        if event not in self._event_handlers:
            return
        if callback is None:
            del self._event_handlers[event]
            return
        handlers = self._event_handlers[event]
        if callback in handlers:
            handlers.remove(callback)
        if not handlers:
            del self._event_handlers[event]

    async def wait_for(self, event: str, timeout: typing.Optional[float] = None) -> typing.Any:
        """
        Wait until *event* is emitted and return its payload.

        Args:
            event: The event type to wait for (from RealtimeEvents enum)
            timeout: Maximum seconds to wait; ``None`` waits indefinitely

        Raises:
            asyncio.TimeoutError: If the event is not emitted within *timeout*

        Example:
            ```python
            await connection.commit()
            data = await connection.wait_for(RealtimeEvents.COMMITTED_TRANSCRIPT, timeout=10)
            print(data["transcript"])
            ```
        """
        future: "asyncio.Future[typing.Any]" = asyncio.get_running_loop().create_future()

        def _resolver(*args: typing.Any) -> None:
            if not future.done():
                future.set_result(args[0] if len(args) == 1 else args)

        self.on(event, _resolver)
        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            self.off(event, _resolver)

    def _emit(self, event: str, *args) -> None:
        """Emit an event to all registered handlers"""
        for queue in list(self._event_queues):
            queue.put_nowait((event, args[0] if args else None))
        if event in self._event_handlers:
            for handler in list(self._event_handlers[event]):
                try:
                    result = handler(*args)
                    if asyncio.iscoroutine(result):
                        task = asyncio.get_running_loop().create_task(result)
                        self._callback_tasks.add(task)
                        task.add_done_callback(self._on_callback_task_done)
                except Exception as e:
                    print(f"Error in event handler for {event}: {e}")

    def _on_callback_task_done(self, task: asyncio.Task) -> None:
        self._callback_tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            print(f"Error in async event handler: {task.exception()}")

    async def events(
        self, events: typing.Optional[typing.Iterable[str]] = None
    ) -> typing.AsyncIterator[typing.Tuple[str, RealtimeEventPayload]]:
        """
        Iterate over events emitted by the connection as ``(event, payload)`` tuples.

        Iteration ends when the connection closes.

        Args:
            events: Optional collection of event types to yield. When ``None``,
                every event (except CLOSE) is yielded.

        Example:
            ```python
            async for event, payload in connection.events():
                if event == RealtimeEvents.PARTIAL_TRANSCRIPT:
                    print(payload["transcript"])
            ```
        """
        wanted = {_event_key(e) for e in events} if events is not None else None
        queue: "asyncio.Queue[typing.Tuple[str, typing.Any]]" = asyncio.Queue()
        self._event_queues.append(queue)
        try:
            while True:
                event, payload = await queue.get()
                if _event_key(event) == RealtimeEvents.CLOSE.value:
                    return
                if wanted is None or _event_key(event) in wanted:
                    yield event, payload
        finally:
            self._event_queues.remove(queue)

    async def transcripts(
        self, include_partial: bool = False
    ) -> typing.AsyncIterator[CommittedTranscriptEvent]:
        """
        Iterate over transcript payloads until the connection closes.

        Args:
            include_partial: When ``True``, partial transcripts are yielded in
                addition to committed ones.

        Example:
            ```python
            async for transcript in connection.transcripts():
                print(transcript["transcript"])
            ```
        """
        wanted: typing.List[str] = [
            RealtimeEvents.COMMITTED_TRANSCRIPT,
            RealtimeEvents.COMMITTED_TRANSCRIPT_WITH_TIMESTAMPS,
        ]
        if include_partial:
            wanted.append(RealtimeEvents.PARTIAL_TRANSCRIPT)
        async for _, payload in self.events(wanted):
            yield typing.cast(CommittedTranscriptEvent, payload)

    def __aiter__(self) -> typing.AsyncIterator[typing.Tuple[str, RealtimeEventPayload]]:
        return self.events()

    async def _start_message_handler(self) -> None:
        """Start handling incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    message_type = data.get("message_type")

                    # Try to match message_type to a known event
                    try:
                        event = RealtimeEvents(message_type)
                        self._emit(event, data)

                        # Also emit generic ERROR event for specific error types
                        error_events = {
                            RealtimeEvents.AUTH_ERROR,
                            RealtimeEvents.QUOTA_EXCEEDED,
                            RealtimeEvents.COMMIT_THROTTLED,
                            RealtimeEvents.TRANSCRIBER_ERROR,
                            RealtimeEvents.UNACCEPTED_TERMS_ERROR,
                            RealtimeEvents.RATE_LIMITED,
                            RealtimeEvents.INPUT_ERROR,
                            RealtimeEvents.QUEUE_OVERFLOW,
                            RealtimeEvents.RESOURCE_EXHAUSTED,
                            RealtimeEvents.SESSION_TIME_LIMIT_EXCEEDED,
                            RealtimeEvents.CHUNK_SIZE_EXCEEDED,
                            RealtimeEvents.INSUFFICIENT_AUDIO_ACTIVITY,
                        }
                        if event in error_events:
                            self._emit(RealtimeEvents.ERROR, data)
                    except ValueError:
                        # Unknown message type, ignore
                        pass
                except json.JSONDecodeError as e:
                    self._emit(RealtimeEvents.ERROR, {"error": f"Failed to parse message: {e}"})
        except Exception as e:
            self._emit(RealtimeEvents.ERROR, {"error": str(e)})
        finally:
            self._emit(RealtimeEvents.CLOSE)

    async def send(self, data: typing.Dict[str, typing.Any]) -> None:
        """
        Send an audio chunk to the server for transcription.

        Args:
            data: Dictionary containing the following keys:
                - audio_base_64 (str): Base64-encoded audio data to transcribe
                - previous_text (str, optional): Previous transcript text to provide context
                  for more accurate transcription

        Raises:
            RuntimeError: If the WebSocket connection is not open

        Example:
            ```python
            # Send audio chunk
            connection.send({
                "audio_base_64": base64_encoded_audio
            })

            # Send audio chunk with context - can only be sent with the first chunk of audio
            connection.send({
                "audio_base_64": base64_encoded_audio,
                "previous_text": "Previously transcribed text for context"
            })
            ```
        """
        if not self.websocket:
            raise RuntimeError("WebSocket is not connected")

        message = {
            "message_type": "input_audio_chunk",
            "audio_base_64": data.get("audio_base_64", ""),
            "commit": False,
            "sample_rate": self.current_sample_rate,
            "previous_text": data.get("previous_text"),
        }

        await self.websocket.send(json.dumps(message))

    async def commit(self) -> None:
        """
        Commits the segment, triggering a COMMITTED_TRANSCRIPT event and clearing the buffer.
        It's recommend to commit often when using CommitStrategy.MANUAL to keep latency low.

        Raises:
            RuntimeError: If the WebSocket connection is not open

        Remarks:
            Only needed when using CommitStrategy.MANUAL.
            When using CommitStrategy.VAD, commits are handled automatically by the server.

        Example:
            ```python
            # Send all audio chunks
            for chunk in audio_chunks:
                connection.send({"audioBase64": chunk})

            # Commit the audio segment
            await connection.commit()
            ```
        """
        if not self.websocket:
            raise RuntimeError("WebSocket is not connected")

        message = {
            "message_type": "input_audio_chunk",
            "audio_base_64": "",
            "commit": True,
            "sample_rate": self.current_sample_rate,
        }

        await self.websocket.send(json.dumps(message))

    async def close(self) -> None:
        """
        Closes the WebSocket connection and cleans up resources.
        This will terminate any ongoing transcription and stop ffmpeg processes if running.

        Remarks:
            After calling close(), this connection cannot be reused.
            Create a new connection if you need to start transcribing again.

        Example:
            ```python
            connection.on(RealtimeEvents.COMMITTED_TRANSCRIPT, async lambda data: (
                print("Committed:", data["transcript"]),
                await connection.close()
            ))
            ```
        """
        await self._cleanup()
        try:
            if self.websocket:
                await self.websocket.close(1000, "User ended conversation")
        finally:
            if self._message_task and not self._message_task.done():
                self._message_task.cancel()
                try:
                    await self._message_task
                except asyncio.CancelledError:
                    pass

    async def _cleanup(self) -> None:
        """Clean up resources like ffmpeg processes"""
        if self.ffmpeg_process:
            self.ffmpeg_process.kill()
            try:
                self.ffmpeg_process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.ffmpeg_process.kill()
            self.ffmpeg_process = None

