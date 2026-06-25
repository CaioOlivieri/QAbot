import ipaddress
import os
import re
import socket
from urllib.parse import urlparse

import httpx

from qabot.tools.fs import list_files


def detect_api_endpoints(project_path: str) -> list[str]:
    urls: set[str] = set()
    pattern = re.compile(r"https?://[^\s\"'`\)]+")
    for filepath in list_files(project_path):
        with open(filepath) as f:
            content = f.read()
        urls.update(url.rstrip(".,;:)]}\"'`") for url in pattern.findall(content))
    return sorted(urls)


def _network_enabled() -> bool:
    """Outbound API testing is opt-in: off unless QABOT_ALLOW_NETWORK is set."""
    return os.environ.get("QABOT_ALLOW_NETWORK", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _resolve_ips(host: str) -> list[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, None)]


def _ssrf_reason(url: str) -> str | None:
    """Refusal reason if the URL targets a non-public address, else None.

    Resolves the host and rejects loopback, private (RFC1918 / unique-local),
    link-local (169.254/16, fe80::/10), reserved, multicast and unspecified
    addresses — the SSRF surface a malicious target repo could point us at.
    """
    host = urlparse(url).hostname
    if not host:
        return "Refused: no host in URL."
    try:
        ips = _resolve_ips(host)
    except socket.gaierror:
        return f"Refused: cannot resolve host {host}."
    for ip_str in ips:
        ip = ipaddress.ip_address(ip_str)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return f"Refused: {host} resolves to non-public address {ip_str}."
    return None


def test_api_endpoint(
    url: str,
    method: str = "GET",
    expected_status: int = 200,
    timeout: int = 10,
) -> dict[str, str | int | bool]:
    def _fail(error: str) -> dict[str, str | int | bool]:
        return {
            "url": url,
            "method": method.upper(),
            "status_code": 0,
            "expected_status": expected_status,
            "passed": False,
            "error": error,
        }

    if not _network_enabled():
        return _fail("Network testing disabled. Set QABOT_ALLOW_NETWORK=1 to enable.")
    reason = _ssrf_reason(url)
    if reason is not None:
        return _fail(reason)
    try:
        response = httpx.request(method.upper(), url, timeout=timeout)
        return {
            "url": url,
            "method": method.upper(),
            "status_code": response.status_code,
            "expected_status": expected_status,
            "passed": response.status_code == expected_status,
            "error": "",
        }
    except Exception as e:
        return _fail(str(e))
