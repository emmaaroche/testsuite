"""Test TokenRateLimitPolicy functionality"""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador, pytest.mark.authorino]


def post_until_rate_limited(client, auth, basic_request, limit):
    """Send requests until quota is exceeded, then send one more to confirm 429"""
    total_tokens = 0

    # Keep sending requests while within token quota
    while total_tokens <= limit:
        response = client.post(
            "/v1/chat/completions",
            auth=auth,
            json={**basic_request, "max_tokens": 30},
        )

        if response.status_code == 429:
            return response, total_tokens

        assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"
        total_tokens += response.extract_tokens()

    # Once over the limit, the next request should be rate limited
    response = client.post(
        "/v1/chat/completions",
        auth=auth,
        json={**basic_request, "max_tokens": 5},
    )
    return response, total_tokens


def test_token_usage_on_request(client, free_user_auth, basic_request):
    """Ensures a request reports token usage"""
    response = client.post("/v1/chat/completions", auth=free_user_auth, json={**basic_request, "max_tokens": 50})
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"
    usage = response.json()["usage"]
    assert usage["total_tokens"] > 0
    assert usage["total_tokens"] <= 50


def test_multiple_requests_under_limit(client, paid_user_auth, basic_request):
    """Ensures multiple requests within the token quota return 200"""
    responses = client.post_many(
        "/v1/chat/completions",
        count=3,
        auth=paid_user_auth,
        json={**basic_request, "max_tokens": 10},
    )
    responses.assert_all(200)


def test_token_rate_limit_free_user(client, free_user_auth, basic_request):
    """Ensures free-tier users are rate limited after exceeding token quota"""
    response, total_tokens = post_until_rate_limited(client, free_user_auth, basic_request, limit=50)
    assert response.status_code == 429, f"Expected 429 after {total_tokens} tokens, but got {response.status_code}"


def test_token_rate_limit_paid_user(client, paid_user_auth, basic_request):
    """Ensures paid-tier users are rate limited after exceeding token quota"""
    response, total_tokens = post_until_rate_limited(client, paid_user_auth, basic_request, limit=100)
    assert response.status_code == 429, f"Expected 429 after {total_tokens} tokens, but got {response.status_code}"
