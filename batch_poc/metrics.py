from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import os
import re
import socket
import time
from typing import Optional, Tuple

import requests


class MetricsReporter(ABC):
    @abstractmethod
    def start(self, pid: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self, pid: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def error(self, pid: int) -> None:
        raise NotImplementedError


class NoopMetricsReporter(MetricsReporter):
    def start(self, pid: int) -> None:
        return

    def stop(self, pid: int) -> None:
        return

    def error(self, pid: int) -> None:
        return


class JavaBatchMetricsReporter(MetricsReporter):
    """
    Implements the same reporting contract as example_monitor.py.
    """

    def __init__(self, environment: str = "jbatch") -> None:
        self.environment = environment
        self._started_at: Optional[float] = None

    @staticmethod
    def _metric_targets() -> Tuple[str, str, str]:
        server = socket.gethostname().split(".")[0]
        if "prod" in server:
            return "fkmetrics", "surv_executing", "surv_history"
        return "metricstest", "davve", "davve"

    @staticmethod
    def _sanitize_job_name(value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9,_-]", "", value)

    def _resolve_object(self) -> str:
        to_job_name = os.getenv("TO_JOB_NAME", "")
        if to_job_name:
            cleaned = self._sanitize_job_name(to_job_name)
            if cleaned:
                return cleaned
        return os.getenv("JOB_NAME", "unknown_job")

    def _resolve_chart(self) -> str:
        return os.getenv("TO_ENV_NAME", "MANUELL")

    def _resolve_user(self) -> str:
        return os.getenv("LOGNAME") or os.getenv("USERNAME") or "unknown"

    def _start_time(self) -> str:
        if self._started_at is None:
            return datetime.now(timezone.utc).isoformat()
        return datetime.fromtimestamp(self._started_at, timezone.utc).isoformat()

    def _elapsed(self) -> str:
        if self._started_at is None:
            return "00:00:00"
        elapsed_seconds = max(0, int(time.time() - self._started_at))
        hours, rem = divmod(elapsed_seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _drop_exec_series(self, metric_host: str, exec_db: str, job_name: str) -> None:
        query = f"DROP SERIES from exec_job where JOB='{job_name}'"
        requests.post(
            f"http://{metric_host}.sfa.se:8086/query",
            params={"db": exec_db},
            data={"q": query},
            timeout=10,
        )

    def _insert_point(self, metric_host: str, db_name: str, payload: str) -> None:
        requests.post(
            f"http://{metric_host}.sfa.se:8086/write",
            params={"db": db_name},
            data=payload,
            timeout=10,
        )

    def _report(self, state: str, pid: int) -> None:
        metric_host, exec_db, history_db = self._metric_targets()
        job_name = self._resolve_object()

        if state == "start":
            object_status = "Executing"
            status_flag = 0
            influx_db = exec_db
        elif state == "error":
            object_status = "Failed"
            status_flag = 1
            influx_db = history_db
        elif state == "stop":
            object_status = "Completed"
            status_flag = 2
            influx_db = history_db
        else:
            return

        self._drop_exec_series(metric_host, exec_db, job_name)

        server = socket.gethostname().split(".")[0]
        chart = self._resolve_chart()
        start_time = self._start_time()
        elapsed = self._elapsed()
        user = self._resolve_user()

        payload = (
            f"exec_job,JOB={job_name} "
            f"Object=\"{job_name}\","
            f"Start_time=\"{start_time}\","
            f"Status=\"{object_status}\","
            f"PID={pid},"
            f"User=\"{user}\","
            f"Server=\"{server}\","
            f"Chart=\"{chart}\","
            f"Environment=\"{self.environment}\","
            f"Elapsed=\"{elapsed}\","
            f"Status_flag={status_flag}"
        )

        self._insert_point(metric_host, influx_db, payload)

    def start(self, pid: int) -> None:
        self._started_at = time.time()
        self._report("start", pid)

    def stop(self, pid: int) -> None:
        self._report("stop", pid)

    def error(self, pid: int) -> None:
        self._report("error", pid)
