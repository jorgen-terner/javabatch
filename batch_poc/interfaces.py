from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class JobResult:
    status: str
    execution_id: Optional[str] = None
    summary: Optional[str] = None


class BatchJobService(ABC):
    """Contract expected by inf-batch-job-app."""

    @abstractmethod
    def startJob(self, job_args: str) -> JobResult:
        raise NotImplementedError

    @abstractmethod
    def statusJob(self, execution_id: str) -> JobResult:
        raise NotImplementedError

    @abstractmethod
    def stopJob(self, job_args: str) -> JobResult:
        raise NotImplementedError

    @abstractmethod
    def restartJob(self, job_args: str) -> JobResult:
        raise NotImplementedError

    @abstractmethod
    def summaryJob(self, execution_id: str) -> JobResult:
        raise NotImplementedError
