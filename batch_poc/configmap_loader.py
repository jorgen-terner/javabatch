from __future__ import annotations

import os
from typing import Optional


def _read_from_mount(configmap_name: str, key: str) -> Optional[str]:
    mount_root = os.getenv("CONFIGMAP_MOUNT_ROOT", "/etc/configmaps")
    mounted_key_file = os.path.join(mount_root, configmap_name, key)
    if os.path.exists(mounted_key_file):
        with open(mounted_key_file, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    return None


def load_batch_type(configmap_name: Optional[str], namespace: Optional[str]) -> str:
    """
    Reads BATCH_TYP from ConfigMap mount first, then Kubernetes API, then env fallback.
    """
    key = "BATCH_TYP"
    if not configmap_name:
        return os.getenv(key, "")

    mounted_value = _read_from_mount(configmap_name, key)
    if mounted_value:
        return mounted_value

    # Lazy import to keep local execution simple when kubernetes is unavailable.
    try:
        from kubernetes import client, config

        config.load_incluster_config()
        api = client.CoreV1Api()
        namespace_to_use = namespace or os.getenv("POD_NAMESPACE", "default")
        cm = api.read_namespaced_config_map(configmap_name, namespace_to_use)
        if cm and cm.data and key in cm.data:
            return cm.data[key]
    except Exception:
        pass

    return os.getenv(key, "")
