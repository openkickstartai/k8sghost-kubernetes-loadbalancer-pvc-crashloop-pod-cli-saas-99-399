"""Tests for K8sGhost scanner — orphaned PVCs, zombie pods, unused LBs."""
import unittest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta
from scanner import KubeScanner, parse_gi, parse_cpu, age_days


def _meta(name, ns="default", days_ago=10, deleting=False):
    m = MagicMock()
    m.name, m.namespace = name, ns
    m.creation_timestamp = datetime.now(timezone.utc) - timedelta(days=days_ago)
    m.deletion_timestamp = datetime.now(timezone.utc) if deleting else None
    return m


def _pvc(name, ns="default", storage="10Gi"):
    p = MagicMock()
    p.metadata = _meta(name, ns)
    p.spec.resources.requests = {"storage": storage}
    return p


def _pod(name, ns="default", vols=None, crash=False, deleting=False):
    p = MagicMock()
    p.metadata = _meta(name, ns, deleting=deleting)
    p.spec.volumes = vols or []
    c = MagicMock()
    c.resources = MagicMock()
    c.resources.requests = {"cpu": "250m", "memory": "512Mi"}
    p.spec.containers = [c]
    p.status.phase = "Running"
    if crash:
        cs = MagicMock()
        cs.state.waiting.reason = "CrashLoopBackOff"
        p.status.container_statuses = [cs]
    else:
        p.status.container_statuses = []
    return p


class TestParseUtils(unittest.TestCase):
    def test_parse_gi_various_units(self):
        self.assertAlmostEqual(parse_gi("10Gi"), 10.0)
        self.assertAlmostEqual(parse_gi("512Mi"), 0.5)
        self.assertAlmostEqual(parse_gi("1Ti"), 1024.0)
        self.assertAlmostEqual(parse_gi("unknown"), 0.0)

    def test_parse_cpu(self):
        self.assertAlmostEqual(parse_cpu("250m"), 0.25)
        self.assertAlmostEqual(parse_cpu("2"), 2.0)

    def test_age_days(self):
        ts = datetime.now(timezone.utc) - timedelta(days=7)
        self.assertEqual(age_days(ts), 7)
        self.assertEqual(age_days(None), 0)


class TestOrphanedPVCs(unittest.TestCase):
    def test_detects_orphaned_pvc(self):
        v1 = MagicMock()
        v1.list_pod_for_all_namespaces.return_value.items = []
        v1.list_persistent_volume_claim_for_all_namespaces.return_value.items = [_pvc("orphan")]
        result = KubeScanner(v1_api=v1).scan_orphaned_pvcs()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "orphan")
        self.assertAlmostEqual(result[0].monthly_cost, 1.0)

    def test_mounted_pvc_not_flagged(self):
        v1 = MagicMock()
        vol = MagicMock()
        vol.persistent_volume_claim.claim_name = "data"
        v1.list_pod_for_all_namespaces.return_value.items = [_pod("app", vols=[vol])]
        v1.list_persistent_volume_claim_for_all_namespaces.return_value.items = [_pvc("data")]
        self.assertEqual(len(KubeScanner(v1_api=v1).scan_orphaned_pvcs()), 0)


class TestZombiePods(unittest.TestCase):
    def test_detects_crashloop(self):
        v1 = MagicMock()
        v1.list_pod_for_all_namespaces.return_value.items = [_pod("crash", crash=True)]
        result = KubeScanner(v1_api=v1).scan_zombie_pods()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].reason, "CrashLoopBackOff")
        self.assertGreater(result[0].monthly_cost, 0)

    def test_healthy_pod_ignored(self):
        v1 = MagicMock()
        v1.list_pod_for_all_namespaces.return_value.items = [_pod("healthy")]
        self.assertEqual(len(KubeScanner(v1_api=v1).scan_zombie_pods()), 0)


class TestUnusedLBs(unittest.TestCase):
    def test_detects_no_endpoint_lb(self):
        v1 = MagicMock()
        svc = MagicMock()
        svc.metadata = _meta("dead-lb")
        svc.spec.type = "LoadBalancer"
        v1.list_service_for_all_namespaces.return_value.items = [svc]
        v1.read_namespaced_endpoints.return_value.subsets = None
        result = KubeScanner(v1_api=v1).scan_unused_lbs()
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0].monthly_cost, 18.0)

    def test_clusterip_ignored(self):
        v1 = MagicMock()
        svc = MagicMock()
        svc.metadata = _meta("internal")
        svc.spec.type = "ClusterIP"
        v1.list_service_for_all_namespaces.return_value.items = [svc]
        self.assertEqual(len(KubeScanner(v1_api=v1).scan_unused_lbs()), 0)


class TestScanAll(unittest.TestCase):
    def test_combines_all_scanners(self):
        v1 = MagicMock()
        v1.list_pod_for_all_namespaces.return_value.items = [_pod("crash", crash=True)]
        v1.list_persistent_volume_claim_for_all_namespaces.return_value.items = [_pvc("orphan")]
        svc = MagicMock()
        svc.metadata, svc.spec.type = _meta("lb"), "LoadBalancer"
        v1.list_service_for_all_namespaces.return_value.items = [svc]
        v1.read_namespaced_endpoints.return_value.subsets = None
        result = KubeScanner(v1_api=v1).scan_all()
        self.assertEqual(len(result), 3)
        total = sum(z.monthly_cost for z in result)
        self.assertGreater(total, 25.0)


if __name__ == "__main__":
    unittest.main()
