import ipaddress
import json
import os
import re
import socket
from urllib.parse import urlparse

import requests

ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
BLOCKED_HEADERS = {
    "host", "connection", "content-length", "transfer-encoding",
    "proxy-authorization", "proxy-connection", "te", "trailer", "upgrade",
}
VARIABLE_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
MAX_RESPONSE_BYTES = 1024 * 1024


def _allowed_hosts():
    return {
        item.strip().lower().rstrip(".")
        for item in os.getenv("OPSPILOT_HTTP_ALLOWED_HOSTS", "").split(",")
        if item.strip()
    }


def _validate_destination(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("HTTP Request only supports HTTPS URLs.")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("URLs with credentials or fragments are not supported.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("The request URL has an invalid port.") from exc
    if port not in (None, 443):
        raise ValueError("Only the standard HTTPS port 443 is allowed.")
    host = parsed.hostname.lower().rstrip(".")
    if host not in _allowed_hosts():
        raise ValueError(
            f"Host '{host}' is not allowlisted. Add it to OPSPILOT_HTTP_ALLOWED_HOSTS."
        )
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP-literal request destinations are not allowed.")
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("The allowlisted host could not be resolved.") from exc
    resolved = {item[4][0] for item in addresses}
    if not resolved or any(not ipaddress.ip_address(item).is_global for item in resolved):
        raise ValueError("The request host resolves to a private or reserved IP address.")
    return parsed


def _substitute(value, variables):
    if isinstance(value, str):
        def replace(match):
            key = match.group(1)
            if key not in variables:
                raise ValueError(f"Workflow variable '{key}' has not been defined.")
            return str(variables[key])
        return VARIABLE_PATTERN.sub(replace, value)
    if isinstance(value, list):
        return [_substitute(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: _substitute(item, variables) for key, item in value.items()}
    return value


def _json_path(payload, path):
    current = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"Response JSON path '{path}' was not found.")
        current = current[part]
    if isinstance(current, (dict, list)) or current is None:
        raise ValueError(f"Response JSON path '{path}' must resolve to a scalar value.")
    return current


def run_http_action(config, variables=None):
    variables = variables or {}
    method = str(config.get("method", "GET")).upper()
    if method not in ALLOWED_METHODS:
        raise ValueError("Unsupported HTTP method.")
    url = _substitute(str(config.get("url", "")).strip(), variables)
    _validate_destination(url)

    headers = _substitute(config.get("headers") or {}, variables)
    if not isinstance(headers, dict) or len(headers) > 20:
        raise ValueError("HTTP headers must be an object with at most 20 entries.")
    safe_headers = {}
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, (str, int, float)):
            raise ValueError("HTTP header names and values must be simple strings or numbers.")
        if key.lower() in BLOCKED_HEADERS or "\r" in key or "\n" in key:
            raise ValueError(f"HTTP header '{key}' is not permitted.")
        value = str(value)
        if "\r" in value or "\n" in value or len(value) > 2000:
            raise ValueError("HTTP header values must be single-line and at most 2,000 characters.")
        safe_headers[key] = value

    body = _substitute(config.get("body"), variables)
    if body is not None and not isinstance(body, (dict, list, str, int, float, bool)):
        raise ValueError("HTTP request body must be JSON-compatible.")
    if len(json.dumps(body, ensure_ascii=False)) > 100000:
        raise ValueError("HTTP request body exceeds the 100 KB limit.")

    response = None
    try:
        response = requests.request(
            method,
            url,
            headers=safe_headers,
            json=body,
            timeout=(3, 10),
            allow_redirects=False,
            stream=True,
        )
        if 300 <= response.status_code < 400:
            raise ValueError("HTTP redirects are blocked for workflow requests.")
        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=16384):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise ValueError("HTTP response exceeded the 1 MB size limit.")
            chunks.append(chunk)
        raw_body = b"".join(chunks)
        if not 200 <= response.status_code < 300:
            raise ValueError(f"HTTP request returned status code {response.status_code}.")
        try:
            response_payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            response_payload = None
        extracted = {}
        extraction = config.get("extract") or {}
        if extraction and response_payload is None:
            raise ValueError("Response extraction requires a valid JSON response.")
        for variable_name, path in extraction.items():
            extracted[variable_name] = _json_path(response_payload, path)
        return {
            "method": method,
            "status_code": response.status_code,
            "variables": extracted,
        }
    except requests.Timeout as exc:
        raise ValueError("HTTP request timed out after 10 seconds.") from exc
    except requests.RequestException as exc:
        raise ValueError("HTTP request failed. Check the allowlisted endpoint and connection.") from exc
    finally:
        if response is not None:
            response.close()
