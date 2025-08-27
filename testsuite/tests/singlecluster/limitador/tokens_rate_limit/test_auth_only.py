"""Tests for API key authentication for TRLP"""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino]


def test_free_tier_key(client, free_user_auth, basic_request):
    """Ensures a valid free-tier API key returns 200"""
    response = client.post("/v1/chat/completions", auth=free_user_auth, json={**basic_request, "max_tokens": 5})
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"


def test_paid_tier_key(client, paid_user_auth, basic_request):
    """Ensures a valid paid-tier API key returns 200"""
    response = client.post("/v1/chat/completions", auth=paid_user_auth, json={**basic_request, "max_tokens": 10})
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"


def test_invalid_api_key(client, basic_request):
    """Ensures an invalid API key is rejected with 401 Unauthorized"""
    response = client.post("/v1/chat/completions", headers={"Authorization": "APIKEY invalid"}, json=basic_request)
    assert response.status_code == 401, f"Expected status code 401, but got {response.status_code}"


def test_missing_api_key(client, basic_request):
    """Ensures requests without an API key are rejected with 401 Unauthorized"""
    response = client.post("/v1/chat/completions", json=basic_request)
    assert response.status_code == 401, f"Expected status code 401, but got {response.status_code}"
