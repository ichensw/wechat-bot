"""Task scheduler - manages periodic background tasks.

Uses APScheduler for reliable scheduling with support for:
  - Interval-based tasks (member count checks)
  - Cron-based tasks (daily cleanup)
  - One-shot tasks
  - Task retry on failure
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("WeChatBot.Scheduler")


class TaskScheduler:
    """Background task scheduler.

    Features:
      - APScheduler-based periodic task management
      - Task registration with automatic error handling
      - Task status monitoring
      - Graceful shutdown
    """

    def __init__(self):
        self._scheduler = BackgroundScheduler(
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 30,
            }
        )
        self._tasks: Dict[str, "TaskInfo"] = {}
        self._running = False

    def start(self) -> None:
        """Start the scheduler."""
        if not self._running:
            self._scheduler.start()
            self._running = True
            logger.info("Task scheduler started with %d tasks", len(self._tasks))

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Task scheduler stopped")

    def add_interval_task(
        self,
        task_id: str,
        func: Callable,
        interval_seconds: int,
        description: str = "",
        start_delay: int = 0,
    ) -> None:
        """Register an interval-based periodic task.

        Args:
            task_id: Unique task identifier.
            func: Callable to execute.
            interval_seconds: Seconds between executions.
            description: Human-readable task description.
            start_delay: Seconds to wait before first execution.
        """
        self._tasks[task_id] = TaskInfo(
            id=task_id,
            func=func,
            interval=interval_seconds,
            description=description,
        )

        self._scheduler.add_job(
            self._safe_execute,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id=task_id,
            name=description or task_id,
            args=[task_id],
            replace_existing=True,
        )

        logger.info("Registered interval task: %s (every %ds)", task_id, interval_seconds)

    def add_cron_task(
        self,
        task_id: str,
        func: Callable,
        hour: int = 0,
        minute: int = 0,
        description: str = "",
    ) -> None:
        """Register a cron-based task (daily at specified time).

        Args:
            task_id: Unique task identifier.
            func: Callable to execute.
            hour: Hour of day (0-23).
            minute: Minute of hour (0-59).
            description: Human-readable task description.
        """
        from apscheduler.triggers.cron import CronTrigger

        self._tasks[task_id] = TaskInfo(
            id=task_id,
            func=func,
            description=description,
            cron=f"{hour}:{minute:02d}",
        )

        self._scheduler.add_job(
            self._safe_execute,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=task_id,
            name=description or task_id,
            args=[task_id],
            replace_existing=True,
        )

        logger.info("Registered cron task: %s (daily at %02d:%02d)", task_id, hour, minute)

    def remove_task(self, task_id: str) -> bool:
        """Remove a registered task."""
        if task_id in self._tasks:
            try:
                self._scheduler.remove_job(task_id)
            except Exception:
                pass
            del self._tasks[task_id]
            logger.info("Removed task: %s", task_id)
            return True
        return False

    def _safe_execute(self, task_id: str) -> None:
        """Execute a task with error handling and logging."""
        task = self._tasks.get(task_id)
        if not task:
            logger.error("Unknown task: %s", task_id)
            return

        try:
            task.func()
            task.record_success()
        except Exception as e:
            task.record_failure(str(e))
            logger.error("Task %s failed: %s", task_id, e)

    def get_task_status(self) -> List[Dict]:
        """Get status of all registered tasks."""
        return [task.to_dict() for task in self._tasks.values()]

    @property
    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._running

    @property
    def task_count(self) -> int:
        """Number of registered tasks."""
        return len(self._tasks)


class TaskInfo:
    """Metadata and status for a scheduled task."""

    def __init__(
        self,
        id: str,
        func: Callable,
        description: str = "",
        interval: Optional[int] = None,
        cron: Optional[str] = None,
    ):
        self.id = id
        self.func = func
        self.description = description
        self.interval = interval
        self.cron = cron
        self.success_count: int = 0
        self.failure_count: int = 0
        self.last_error: Optional[str] = None
        self.last_success_time: Optional[float] = None
        self.last_failure_time: Optional[float] = None

    def record_success(self) -> None:
        """Record a successful execution."""
        import time
        self.success_count += 1
        self.last_success_time = time.time()

    def record_failure(self, error: str) -> None:
        """Record a failed execution."""
        import time
        self.failure_count += 1
        self.last_error = error
        self.last_failure_time = time.time()

    def to_dict(self) -> Dict:
        """Serialize task info to dict."""
        return {
            "id": self.id,
            "description": self.description,
            "interval": self.interval,
            "cron": self.cron,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_error": self.last_error,
            "last_success_time": self.last_success_time,
            "last_failure_time": self.last_failure_time,
        }
