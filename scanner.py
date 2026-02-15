"""K8sGhost core scanner — detects zombie Kubernetes resources with cost estimates."""
from dataclasses import dataclass
from typing import List
from datetime import datetime, timezone

COST = {"lb": 18.0, "pvc_gb": 0.10, "cpu": 30.0, "mem_gb": 4.0}


@dataclass
class Zombie:
    kind: str
    name: str
    namespace: str
    reason: str
    monthly_cost: float
    age_days: int = 0


def parse_gi(s) -> float:
    s = str(s)
    for suffix, mult in [("Ti", 1024), ("Gi", 1), ("Mi", 1 / 1024)]:
        if s.endswith(suffix):
            return float(s[: -2]) * mult
    return 0.0


def parse_cpu(s) -> float:
    s = str(s)
    return float(s[:-1]) / 1000 if s.endswith("m") else float(s)


def age_days(ts) -> int:
    if not ts or not isinstance(ts, datetime):
        return 0
    t = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - t).days)


class KubeScanner:
    def __init__(self, v1_api=None, kubeconfig=None, context=None):
        if v1_api:
            self.v1 = v1_api
        else:
            from kubernetes import client, config
            try:
                config.load_kube_config(config_file=kubeconfig, context=context)
            except Exception:
                config.load_incluster_config()
            self.v1 = client.CoreV1Api()

    def _pods(self, ns=None):
        return self.v1.list_namespaced_pod(ns) if ns else self.v1.list_pod_for_all_namespaces()

    def _pvcs(self, ns=None):
        if ns:
            return self.v1.list_namespaced_persistent_volume_claim(ns)
        return self.v1.list_persistent_volume_claim_for_all_namespaces()

    def _svcs(self, ns=None):
        return self.v1.list_namespaced_service(ns) if ns else self.v1.list_service_for_all_namespaces()

    def scan_orphaned_pvcs(self, ns=None) -> List[Zombie]:
        used = set()
        for p in self._pods(ns).items:
            for v in (p.spec.volumes or []):
                if v.persistent_volume_claim:
                    used.add((p.metadata.namespace, v.persistent_volume_claim.claim_name))
        result = []
        for pvc in self._pvcs(ns).items:
            if (pvc.metadata.namespace, pvc.metadata.name) not in used:
                gb = parse_gi(pvc.spec.resources.requests.get("storage", "0Gi"))
                result.append(Zombie("PVC", pvc.metadata.name, pvc.metadata.namespace,
                    "Not mounted by any pod", gb * COST["pvc_gb"],
                    age_days(pvc.metadata.creation_timestamp)))
        return result

    def scan_zombie_pods(self, ns=None) -> List[Zombie]:
        result = []
        for p in self._pods(ns).items:
            reason = None
            for cs in (p.status.container_statuses or []):
                if cs.state and cs.state.waiting:
                    if cs.state.waiting.reason == "CrashLoopBackOff":
                        reason = "CrashLoopBackOff"
                        break
            if p.metadata.deletion_timestamp and p.status.phase == "Running":
                reason = "Stuck terminating"
            if not reason:
                continue
            cpu, mem = 0.0, 0.0
            for c in (p.spec.containers or []):
                req = (c.resources.requests or {}) if c.resources else {}
                cpu += parse_cpu(req.get("cpu", "0"))
                mem += parse_gi(req.get("memory", "0Mi"))
            result.append(Zombie("Pod", p.metadata.name, p.metadata.namespace,
                reason, cpu * COST["cpu"] + mem * COST["mem_gb"],
                age_days(p.metadata.creation_timestamp)))
        return result

    def scan_unused_lbs(self, ns=None) -> List[Zombie]:
        result = []
        for svc in self._svcs(ns).items:
            if svc.spec.type != "LoadBalancer":
                continue
            ep = self.v1.read_namespaced_endpoints(svc.metadata.name, svc.metadata.namespace)
            if not any(s.addresses for s in (ep.subsets or [])):
                result.append(Zombie("Service/LB", svc.metadata.name, svc.metadata.namespace,
                    "No healthy endpoints", COST["lb"],
                    age_days(svc.metadata.creation_timestamp)))
        return result

    def scan_all(self, ns=None) -> List[Zombie]:
        return self.scan_orphaned_pvcs(ns) + self.scan_zombie_pods(ns) + self.scan_unused_lbs(ns)
