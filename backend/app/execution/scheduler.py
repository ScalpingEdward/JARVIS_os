import os
from threading import Event, Lock, Thread

from .service import AutonomousExecutionService, autonomous_execution_service


class WorkflowScheduler:
    def __init__(
        self,
        service: AutonomousExecutionService = autonomous_execution_service,
        interval_seconds: float | None = None,
    ) -> None:
        self.service = service
        self.interval_seconds = interval_seconds or float(
            os.getenv("JARVIS_SCHEDULER_INTERVAL_SECONDS", "5")
        )
        self._stop = Event()
        self._thread: Thread | None = None
        self._lock = Lock()
        self.last_error: str | None = None
        self.cycles = 0

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self.running:
                return
            self._stop.clear()
            self._thread = Thread(target=self._loop, name="jarvis-workflow-scheduler", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        with self._lock:
            thread = self._thread
            if thread is None:
                return
            self._stop.set()
        thread.join(timeout=timeout)
        with self._lock:
            self._thread = None

    def run_once(self) -> int:
        try:
            results = self.service.tick_active()
            self.cycles += 1
            self.last_error = None
            return len(results)
        except Exception as exc:  # scheduler must survive one failed workflow cycle
            self.last_error = str(exc)
            self.cycles += 1
            return 0

    def status(self) -> dict[str, object]:
        return {
            "running": self.running,
            "interval_seconds": self.interval_seconds,
            "cycles": self.cycles,
            "last_error": self.last_error,
        }

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self.run_once()


workflow_scheduler = WorkflowScheduler()
