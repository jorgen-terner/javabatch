#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import sys

from batch_poc.configmap_loader import load_batch_type
from batch_poc.job_dispatcher import ScriptJobRequest, create_script_job, infer_namespace
from batch_poc.javabatch_service import JavaBatchService
from batch_poc.metrics import JavaBatchMetricsReporter, NoopMetricsReporter


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="inf-batch-job-app")
    parser.add_argument("--job-config", required=True, help="Path to endpoint config file")
    parser.add_argument("--token", default="", help="FKST token")
    parser.add_argument(
        "--action",
        required=True,
        choices=["start", "status", "stop", "restart", "summary", "help", "dispatch-script-job"],
        help="Action to run",
    )
    parser.add_argument("--job-args", default="", help="Job arguments or execution id")
    parser.add_argument("--configmap-name", default="", help="ConfigMap that contains BATCH_TYP")
    parser.add_argument("--namespace", default="", help="ConfigMap namespace")
    parser.add_argument("--script-image", default="", help="Script image to run as separate Kubernetes Job")
    parser.add_argument(
        "--script-action",
        default="restart",
        choices=["start", "status", "stop", "restart", "summary", "help"],
        help="Action passed to script image",
    )
    parser.add_argument(
        "--endpoints-configmap-name",
        default="springbatch-endpoints",
        help="ConfigMap containing endpoint file for the script",
    )
    parser.add_argument(
        "--endpoint-config-filename",
        default="examplejob.ini",
        help="Filename in endpoints ConfigMap mounted for script job",
    )
    parser.add_argument(
        "--script-job-name-prefix",
        default="javabatch-script",
        help="Prefix for generated Kubernetes script Job name",
    )
    return parser


def select_metrics_reporter(configmap_name: str, namespace: str):
    batch_type = load_batch_type(configmap_name=configmap_name, namespace=namespace).strip().upper()
    if batch_type == "JAVABATCH":
        return JavaBatchMetricsReporter()
    return NoopMetricsReporter()


def _print_result(status: str, execution_id: str = "", summary: str = "") -> None:
    payload = {
        "status": status,
        "executionId": execution_id,
        "summary": summary,
    }
    print(json.dumps(payload, ensure_ascii=True))


def _dispatch_script_job(args) -> str:
    if not args.script_image:
        raise RuntimeError("--script-image is required when --action dispatch-script-job")

    namespace = infer_namespace(args.namespace)
    request = ScriptJobRequest(
        namespace=namespace,
        job_name_prefix=args.script_job_name_prefix,
        image=args.script_image,
        action=args.script_action,
        job_args=args.job_args,
        token=args.token,
        endpoints_configmap_name=args.endpoints_configmap_name,
        configmap_name=args.configmap_name,
        endpoint_config_filename=args.endpoint_config_filename,
    )
    return create_script_job(request)


def main(argv: list[str]) -> int:
    args = build_arg_parser().parse_args(argv)
    metrics = select_metrics_reporter(args.configmap_name, args.namespace)

    def signal_handler(signum, _frame):
        print(f"signal {signum} detected, exiting gracefully", flush=True)
        metrics.error(os.getpid())
        raise SystemExit(1)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if os.name != "nt":
        signal.signal(signal.SIGABRT, signal_handler)
        signal.signal(signal.SIGHUP, signal_handler)
        signal.signal(signal.SIGQUIT, signal_handler)

    try:
        if args.action == "dispatch-script-job":
            job_name = _dispatch_script_job(args)
            _print_result(status="DISPATCHED", execution_id=job_name, summary="Script job created")
            return 0

        service = JavaBatchService(config_path=args.job_config, token=args.token, metrics=metrics)

        if args.action == "start":
            result = service.startJob(args.job_args)
        elif args.action == "status":
            result = service.statusJob(args.job_args)
        elif args.action == "stop":
            result = service.stopJob(args.job_args)
        elif args.action == "restart":
            result = service.restartJob(args.job_args)
        elif args.action == "summary":
            result = service.summaryJob(args.job_args)
        elif args.action == "help":
            result = service.helpJob()
        else:
            raise RuntimeError("Unsupported action")

        _print_result(result.status, result.execution_id or "", result.summary or "")
        return 0
    except Exception as exc:
        metrics.error(os.getpid())
        _print_result(status="ERROR", summary=str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
