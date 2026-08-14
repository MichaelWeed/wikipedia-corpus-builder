import contextlib
from collections.abc import Callable

from corpussieve.contracts.events import ProgressEvent


class EventBus:
    """Publish-subscribe bus for progress events."""

    def __init__(self) -> None:
        self._listeners: list[Callable[[ProgressEvent], None]] = []

    def subscribe(self, callback: Callable[[ProgressEvent], None]) -> None:
        """Register a callback for progress events."""
        self._listeners.append(callback)

    def publish(self, event: ProgressEvent) -> None:
        """Broadcast progress event to all registered listeners."""
        for callback in self._listeners:
            with contextlib.suppress(Exception):
                callback(event)
