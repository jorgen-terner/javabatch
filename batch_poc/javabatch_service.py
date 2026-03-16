from __future__ import annotations

import configparser
import os
import sys
import time
from typing import Dict

import requests

from batch_poc.interfaces import BatchJobService, JobResult
from batch_poc.metrics import MetricsReporter


class JavaBatchService(BatchJobService):
    def __init__(self, config_path: str, token: str, metrics: MetricsReporter) -> None:
        self.config_path = config_path
        self.token = token
        self.metrics = metrics
        self.endpoints = self._load_endpoints(config_path)

    @staticmethod
    def _load_endpoints(config_path: str) -> Dict[str, str]:
        parser = configparser.RawConfigParser()
        parser.read(config_path)
        section = parser["endpoints"]
        return {
            "start": section.get("springbatchpy.v2.start", ""),
            "status": section.get("springbatchpy.v2.status", ""),
            "stop": section.get("springbatchpy.v2.stop", ""),
            "restart": section.get("springbatchpy.v2.restart", ""),
            "summary": section.get("springbatchpy.v2.summary", ""),
            "help": section.get("springbatchpy.v2.help", ""),
        }

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json; charset=utf-8",
            "FKST": self.token,
        }

    @staticmethod
    def _join_url(base_url: str, suffix: str) -> str:
        return f"{base_url.rstrip('/')}/{suffix}"

    def _status_poll(self, execution_id: str) -> JobResult:
        status_url = self._join_url(self.endpoints["status"], execution_id)
        summary_url_base = self.endpoints["summary"]
        faults = 0

        while True:
            time.sleep(5)
            response = requests.get(status_url, headers=self._headers(), timeout=30)
            if str(response.status_code).startswith("2"):
                text = response.text
                if "COMPLETED" in text:
                    summary = self.summaryJob(execution_id).summary
                    self.metrics.stop(os.getpid())
                    return JobResult(status="COMPLETED", execution_id=execution_id, summary=summary)
                if "STARTED" in text or "STARTING" in text:
                    continue
                self.metrics.error(os.getpid())
                raise RuntimeError(f"Unexpected job status response: {text}")

            faults += 1
            if faults >= 5:
                self.metrics.error(os.getpid())
                raise RuntimeError(response.text)

    def startJob(self, job_args: str) -> JobResult:
        self.metrics.start(os.getpid())
        url = self._join_url(self.endpoints["start"], job_args)
        response = requests.get(url, headers=self._headers(), timeout=30)
        if not str(response.status_code).startswith("2"):
            self.metrics.error(os.getpid())
            raise RuntimeError(response.text)

        execution_id = response.text.strip()
        return self._status_poll(execution_id)

    def statusJob(self, execution_id: str) -> JobResult:
        self.metrics.start(os.getpid())
        url = self._join_url(self.endpoints["status"], execution_id)
        response = requests.get(url, headers=self._headers(), timeout=30)
        if not str(response.status_code).startswith("2"):
            self.metrics.error(os.getpid())
            raise RuntimeError(response.text)
        self.metrics.stop(os.getpid())
        return JobResult(status=response.text.strip(), execution_id=execution_id)

    def stopJob(self, job_args: str) -> JobResult:
        self.metrics.start(os.getpid())
        url = self._join_url(self.endpoints["stop"], job_args)
        response = requests.get(url, headers=self._headers(), timeout=30)
        if not str(response.status_code).startswith("2"):
            self.metrics.error(os.getpid())
            raise RuntimeError(response.text)
        self.metrics.stop(os.getpid())
        return JobResult(status="STOPPED", execution_id=response.text.strip())

    def restartJob(self, job_args: str) -> JobResult:
        self.metrics.start(os.getpid())
        url = self._join_url(self.endpoints["restart"], job_args)
        response = requests.get(url, headers=self._headers(), timeout=30)
        if not str(response.status_code).startswith("2"):
            self.metrics.error(os.getpid())
            raise RuntimeError(response.text)

        execution_id = response.text.strip()
        result = self._status_poll(execution_id)
        return JobResult(status=result.status, execution_id=execution_id, summary=result.summary)

    def summaryJob(self, execution_id: str) -> JobResult:
        url = self._join_url(self.endpoints["summary"], execution_id)
        response = requests.get(url, headers=self._headers(), timeout=30)
        if not str(response.status_code).startswith("2"):
            raise RuntimeError(response.text)
        return JobResult(status="SUMMARY", execution_id=execution_id, summary=response.text)

    def helpJob(self) -> JobResult:
        help_url = self.endpoints["help"]
        response = requests.get(help_url, headers=self._headers(), timeout=30)
        if not str(response.status_code).startswith("2"):
            raise RuntimeError(response.text)
        return JobResult(status="HELP", summary=response.text)
