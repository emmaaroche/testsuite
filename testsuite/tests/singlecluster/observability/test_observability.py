"""
Tests the enabling and disabling of observability configuration via the Kuadrant CR
"""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.disruptive]

SERVICE_MONITOR_METRICS = [
    "controller_runtime_active_workers",
    "controller_runtime_terminal_reconcile_errors_total",
    "controller_runtime_reconcile_total",
    "controller_runtime_webhook_panics_total",
    "controller_runtime_reconcile_panics_total",
    "workqueue_work_duration_seconds_bucket",
    "workqueue_work_duration_seconds_count",
    "workqueue_queue_duration_seconds_bucket",
    "workqueue_queue_duration_seconds_count",
    "workqueue_retries_total",
    "workqueue_unfinished_work_seconds",
    "go_goroutines",
    "go_threads",
    "go_memstats_alloc_bytes",
    "go_memstats_alloc_bytes_total",
    "go_memstats_heap_alloc_bytes",
    "go_memstats_heap_objects",
    "go_memstats_mallocs_total",
    "go_memstats_frees_total",
]

POD_MONITOR_METRICS = [
    "istio_requests_total",
    "istio_response_bytes_count",
    "istio_response_bytes_sum",
    "istio_agent_cert_expiry_seconds",
    "istio_agent_outgoing_latency",
    "istio_agent_go_gc_duration_seconds",
    "istio_agent_go_goroutines",
    "istio_agent_go_memstats_alloc_bytes",
    "istio_agent_go_memstats_heap_objects",
    "istio_agent_num_outgoing_requests",
    "istio_agent_process_resident_memory_bytes",
    "istio_agent_process_cpu_seconds_total",
    "istio_agent_scrapes_total",
    "istio_agent_startup_duration_seconds",
    "envoy_cluster_upstream_cx_total",
    "envoy_listener_manager_lds_update_success",
    "envoy_server_uptime",
]


@pytest.fixture(scope="module")
def kuadrant(kuadrant, request):
    """Extends kuadrant fixture to enable observability"""
    kuadrant.set_observability(True)

    def _reset():
        kuadrant.set_observability(False)

    request.addfinalizer(_reset)
    return kuadrant


@pytest.fixture(scope="module")
def service_monitor_metrics(service_monitors, prometheus):
    """Return metrics from ServiceMonitors"""
    results = {}

    for sm in service_monitors:
        assert prometheus.is_reconciled(sm), f"{sm.name()} not reconciled in Prometheus"
        prometheus.wait_for_scrape(sm, "/metrics")

        for metric in SERVICE_MONITOR_METRICS:
            data = prometheus.get_metrics(metric, labels={"job": f"{sm.name()}"})
            if data:
                # Collect the same metric from each ServiceMonitor that has it
                results.setdefault(metric, []).extend(data.names)

    return results


@pytest.fixture(scope="module")
def pod_monitor_metrics(client, pod_monitor, prometheus):
    """Return metrics from PodMonitor"""
    responses = client.get_many("/get", 5)
    responses.assert_all(status_code=200)

    assert prometheus.is_reconciled(pod_monitor), f"{pod_monitor.name()} not reconciled in Prometheus"
    prometheus.wait_for_scrape(pod_monitor, "/stats/prometheus")

    results = {}
    for metric in POD_MONITOR_METRICS:
        data = prometheus.get_metrics(metric, labels={"job": f"{pod_monitor.namespace()}/{pod_monitor.name()}"})
        if data:
            results[metric] = data.names

    return results


@pytest.mark.parametrize("metric", SERVICE_MONITOR_METRICS)
def test_service_monitor_metrics(kuadrant, metric, service_monitor_metrics):  # pylint: disable=unused-argument
    """Check ServiceMonitor metrics are present"""
    assert metric in service_monitor_metrics


@pytest.mark.parametrize("metric", POD_MONITOR_METRICS)
def test_pod_monitor_metrics(kuadrant, metric, pod_monitor_metrics, prometheus):  # pylint: disable=unused-argument
    """Check PodMonitor metrics are present and match expected values if predictable"""
    assert metric in pod_monitor_metrics

    # Both source and destination proxies emit metrics for each request, so 5 requests result in 10 metric entries total
    predictable_metrics = {
        "istio_requests_total": 10,
        "istio_response_bytes_count": 10,
    }

    if metric in predictable_metrics:
        result = prometheus.get_metrics(metric)
        total = sum(result.values) if result and result.values else 0
        assert (
            total == predictable_metrics[metric]
        ), f"{metric} expected to be {predictable_metrics[metric]}, got {total}"
