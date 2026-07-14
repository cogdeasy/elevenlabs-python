"""Reconnection and backoff helpers for realtime connections.

Provides :class:`ExponentialBackoff` for computing retry delays and
:func:`connect_with_backoff` for establishing a :class:`RealtimeConnection`
with automatic retries on transient connection failures.
"""

import asyncio
import random
import typing

from .connection import RealtimeConnection

if typing.TYPE_CHECKING:
    from .scribe import RealtimeAudioOptions, RealtimeUrlOptions, ScribeRealtime


class ExponentialBackoff:
    """
    Computes exponentially increasing retry delays with optional jitter.

    Example:
        ```python
        backoff = ExponentialBackoff(initial=0.5, multiplier=2.0, maximum=30.0)
        backoff.next_delay()  # 0.5
        backoff.next_delay()  # 1.0
        backoff.reset()
        ```
    """

    def __init__(
        self,
        initial: float = 0.5,
        multiplier: float = 2.0,
        maximum: float = 30.0,
        jitter: float = 0.0,
    ):
        if initial <= 0:
            raise ValueError("initial must be positive")
        if multiplier < 1.0:
            raise ValueError("multiplier must be >= 1.0")
        if not 0.0 <= jitter <= 1.0:
            raise ValueError("jitter must be between 0.0 and 1.0")
        self.initial = initial
        self.multiplier = multiplier
        self.maximum = maximum
        self.jitter = jitter
        self._attempt = 0

    @property
    def attempt(self) -> int:
        """Number of delays produced since the last reset."""
        return self._attempt

    def next_delay(self) -> float:
        """Return the next delay in seconds and advance the attempt counter."""
        delay = min(self.initial * (self.multiplier**self._attempt), self.maximum)
        self._attempt += 1
        if self.jitter:
            delay *= 1.0 + random.uniform(-self.jitter, self.jitter)
        return delay

    def reset(self) -> None:
        """Reset the attempt counter, e.g. after a successful connection."""
        self._attempt = 0


async def connect_with_backoff(
    scribe: "ScribeRealtime",
    options: typing.Union["RealtimeAudioOptions", "RealtimeUrlOptions"],
    max_attempts: int = 5,
    backoff: typing.Optional[ExponentialBackoff] = None,
    on_retry: typing.Optional[typing.Callable[[int, Exception, float], None]] = None,
) -> RealtimeConnection:
    """
    Connect via :meth:`ScribeRealtime.connect`, retrying transient failures
    with exponential backoff.

    Args:
        scribe: The :class:`ScribeRealtime` instance to connect with
        options: Connection options passed through to ``scribe.connect``
        max_attempts: Total number of connection attempts before giving up
        backoff: Backoff policy; defaults to ``ExponentialBackoff()``
        on_retry: Optional callback invoked before each retry with
            ``(attempt_number, exception, delay_seconds)``

    Returns:
        An established :class:`RealtimeConnection`

    Raises:
        ValueError: If ``max_attempts`` < 1, or immediately on invalid options
            (invalid options are never retried)
        Exception: The last connection error if all attempts fail

    Example:
        ```python
        scribe = ScribeRealtime(api_key="...")
        connection = await connect_with_backoff(
            scribe,
            {"model_id": "scribe_v2_realtime", "audio_format": AudioFormat.PCM_16000, "sample_rate": 16000},
            max_attempts=3,
        )
        ```
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    policy = backoff if backoff is not None else ExponentialBackoff()
    last_error: typing.Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await scribe.connect(typing.cast(typing.Any, options))
        except (ValueError, RuntimeError):
            # Invalid options / missing dependencies won't be fixed by retrying
            raise
        except Exception as e:
            last_error = e
            if attempt == max_attempts:
                break
            delay = policy.next_delay()
            if on_retry is not None:
                on_retry(attempt, e, delay)
            await asyncio.sleep(delay)
    assert last_error is not None
    raise last_error


__all__ = ["ExponentialBackoff", "connect_with_backoff"]
