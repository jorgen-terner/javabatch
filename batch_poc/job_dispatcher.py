from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Dict, List, Optional

from kubernetes import client, config


@dataclass
class ScriptJobRequest:
    namespace: str
    job_name_prefix: str
    image: str
    action: str
    job_args: str
    token: str
    endpoints_configmap_name: str
    configmap_name: str
    endpoint_config_filename: str = "examplejob.ini"
    backoff_limit: int = 0
    ttl_seconds_after_finished: int = 3600
    extra_env: Optional[Dict[str, str]] = None


def _load_k8s_config() -> None:
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()


def _build_args(req: ScriptJobRequest) -> List[str]:
    args = [
        "-j",
        f"/config/{req.endpoint_config_filename}",
    ]

    if req.action == "start":
        args.append("--start")
    elif req.action == "status":
        args.append("--status")
    elif req.action == "stop":
        args.append("--stop")
    elif req.action == "restart":
        args.append("--restart")
    elif req.action == "summary":
        args.append("--summary")
    elif req.action == "help":
        args.append("--help")
    else:
        raise ValueError(f"Unsupported script action: {req.action}")

    if req.job_args:
        args.extend(["-a", req.job_args])
    if req.token:
        args.extend(["-t", req.token])
    return args


def create_script_job(req: ScriptJobRequest) -> str:
    _load_k8s_config()

    batch_api = client.BatchV1Api()
    job_name = f"{req.job_name_prefix}-{req.action}".lower()

    env_vars = [
        client.V1EnvVar(name="POD_NAMESPACE", value=req.namespace),
    ]
    for key, value in (req.extra_env or {}).items():
        env_vars.append(client.V1EnvVar(name=key, value=value))

    container = client.V1Container(
        name="javabatch-script",
        image=req.image,
        args=_build_args(req),
        env=env_vars,
        volume_mounts=[
            client.V1VolumeMount(name="batch-config", mount_path="/config", read_only=True),
            client.V1VolumeMount(
                name="batch-type-config",
                mount_path=f"/etc/configmaps/{req.configmap_name}",
                read_only=True,
            ),
        ],
    )

    pod_spec = client.V1PodSpec(
        restart_policy="Never",
        containers=[container],
        volumes=[
            client.V1Volume(
                name="batch-config",
                config_map=client.V1ConfigMapVolumeSource(name=req.endpoints_configmap_name),
            ),
            client.V1Volume(
                name="batch-type-config",
                config_map=client.V1ConfigMapVolumeSource(name=req.configmap_name),
            ),
        ],
    )

    template = client.V1PodTemplateSpec(spec=pod_spec)
    spec = client.V1JobSpec(
        template=template,
        backoff_limit=req.backoff_limit,
        ttl_seconds_after_finished=req.ttl_seconds_after_finished,
    )

    job = client.V1Job(
        metadata=client.V1ObjectMeta(
            generate_name=f"{job_name}-",
            labels={"app": "inf-batch-job-app", "jobType": "javabatch-script"},
        ),
        spec=spec,
    )

    created = batch_api.create_namespaced_job(namespace=req.namespace, body=job)
    return created.metadata.name or ""


def infer_namespace(explicit_namespace: str) -> str:
    if explicit_namespace:
        return explicit_namespace
    return os.getenv("POD_NAMESPACE", "default")
