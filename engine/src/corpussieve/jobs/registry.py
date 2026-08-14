import threading
from dataclasses import dataclass, field
from typing import Any

from corpussieve.contracts.events import ProgressEvent


@dataclass
class ActiveBuild:
    """In-process tracking for one background build thread.

    Lives only for the lifetime of the serving process — a fresh server
    process (e.g. after a desktop restart) has no entries, so status/cancel
    requests for jobs from a prior process fall back to the persisted
    `JobStore` row instead (see `dispatch_method`'s `build.status` handler).
    """

    cancel_event: threading.Event
    status: str = "running"  # running | succeeded | failed | cancelled
    latest_progress: ProgressEvent | None = None
    error: str | None = None
    report: dict[str, Any] | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


class BuildRegistry:
    """Tracks active/finished background build jobs for the current process.

    Guards its own dict with a lock since entries are written from build
    worker threads and read from the stdin-dispatch thread concurrently.
    """

    def __init__(self) -> None:
        self._builds: dict[str, ActiveBuild] = {}
        self._registry_lock = threading.Lock()

    def register(self, job_id: str, cancel_event: threading.Event) -> ActiveBuild:
        entry = ActiveBuild(cancel_event=cancel_event)
        with self._registry_lock:
            self._builds[job_id] = entry
        return entry

    def get(self, job_id: str) -> ActiveBuild | None:
        with self._registry_lock:
            return self._builds.get(job_id)

    def update_progress(self, job_id: str, event: ProgressEvent) -> None:
        entry = self.get(job_id)
        if not entry:
            return
        with entry.lock:
            entry.latest_progress = event

    def finish(
        self,
        job_id: str,
        *,
        report: dict[str, Any] | None = None,
        error: str | None = None,
        cancelled: bool = False,
    ) -> None:
        entry = self.get(job_id)
        if not entry:
            return
        with entry.lock:
            if cancelled:
                entry.status = "cancelled"
            elif error:
                entry.status = "failed"
                entry.error = error
            else:
                entry.status = "succeeded"
                entry.report = report

    def request_cancel(self, job_id: str) -> bool:
        """Signal cancellation for job_id. Returns False if it isn't tracked."""
        entry = self.get(job_id)
        if not entry:
            return False
        entry.cancel_event.set()
        return True


_REGISTRY = BuildRegistry()


def get_build_registry() -> BuildRegistry:
    """Return the process-wide build registry singleton."""
    return _REGISTRY
