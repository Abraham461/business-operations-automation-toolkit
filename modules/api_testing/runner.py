import requests
from urllib.parse import urlparse


def run_api_test(url, method="GET", body=None, expected_status=200, timeout=15):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Enter a valid HTTP or HTTPS URL.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded credentials are not supported.")

    method = method.upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise ValueError("Unsupported HTTP method.")

    response = requests.request(
        method,
        url,
        json=body,
        timeout=timeout,
        headers={"Accept": "application/json"},
        allow_redirects=False,
    )

    try:
        response_body = response.json()
    except ValueError:
        response_body = response.text[:5000]

    return {
        "success": response.status_code == expected_status,
        "method": method,
        "url": url,
        "status_code": response.status_code,
        "expected_status": expected_status,
        "elapsed_ms": round(response.elapsed.total_seconds() * 1000, 2),
        "response_headers": dict(response.headers),
        "response_body": response_body,
    }
