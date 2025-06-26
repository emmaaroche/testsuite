"""Conftest for observability tests"""

import backoff
import pytest
from openshift_client import selector

from testsuite.gateway import GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.kubernetes.monitoring.pod_monitor import PodMonitor
from testsuite.kubernetes.monitoring.service_monitor import ServiceMonitor


@pytest.fixture(scope="module")
def commit():
    """Override the commit fixture to do nothing"""
    return None


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, wildcard_domain, module_label):
    """Create and configure Gateway with module scope"""
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": module_label})
    gw.add_listener(GatewayListener(hostname=wildcard_domain))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module", autouse=True)
def no_observability_metrics_before_enable(prometheus):
    """Verify no Kuadrant-related observability targets are active before enabling observability"""

    @backoff.on_predicate(backoff.constant, interval=5, max_tries=12, jitter=None)
    def targets_cleared():
        targets = prometheus.get_active_targets()
        return all(
            "operator-monitor" not in t.get("labels", {}).get("job", "")
            and "pod-monitor" not in t.get("labels", {}).get("job", "")
            for t in targets
        )

    if not targets_cleared():
        raise AssertionError("Observability targets still present in Prometheus before enabling observability")


@pytest.fixture(scope="module")
def service_monitors(cluster, testconfig):
    """Return all 4 expected ServiceMonitors created by enabling observability"""
    expected_names = [
        "servicemonitor/authorino-operator-monitor",
        "servicemonitor/dns-operator-monitor",
        "servicemonitor/kuadrant-operator-monitor",
        "servicemonitor/limitador-operator-monitor",
    ]

    context = cluster.change_project(testconfig["service_protection"]["system_project"]).context

    @backoff.on_predicate(backoff.constant, interval=5, max_tries=12, jitter=None)
    def wait_for_monitors():
        monitors = []
        for name in expected_names:
            result = selector(name, static_context=context).objects(cls=ServiceMonitor)
            if len(result) != 1:
                return None
            monitors.append(result[0])
        return monitors

    all_monitors = wait_for_monitors()
    if not all_monitors:
        raise AssertionError(f"Missing one or more expected ServiceMonitors: {expected_names}")

    return all_monitors


@pytest.fixture(scope="module")
def pod_monitor(cluster):
    """Return PodMonitor created by enabling observability"""

    @backoff.on_predicate(backoff.constant, interval=5, max_tries=12, jitter=None)
    def wait_for_monitor():
        result = selector("podmonitor/istio-pod-monitor", static_context=cluster.context).objects(cls=PodMonitor)
        return result[0] if len(result) == 1 else None

    monitor = wait_for_monitor()
    if not monitor:
        raise AssertionError("PodMonitor 'istio-pod-monitor' not found")

    return monitor
