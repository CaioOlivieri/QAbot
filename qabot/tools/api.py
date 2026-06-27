import ipaddress
import os
import re
import socket
from urllib.parse import ParseResult, urlparse

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


def _check_and_pin(host: str) -> tuple[str | None, str | None]:
    """Resolve ``host`` once, validate every address, and pin one to connect to.

    Returns ``(reason, pinned_ip)``. On success ``reason`` is None and
    ``pinned_ip`` is a validated **public** address; on refusal ``reason``
    explains it and ``pinned_ip`` is None. Resolving exactly once here and
    connecting to ``pinned_ip`` (see :func:`_pinned_request`) closes the
    DNS-rebinding gap: a second, independent resolution can no longer swap a
    validated public IP for a private one between check and connect.

    Rejects loopback, private (RFC1918 / unique-local), link-local (169.254/16,
    fe80::/10), reserved, multicast and unspecified addresses — the SSRF surface
    a malicious target repo could point us at.
    """
    try:
        ips = _resolve_ips(host)
    except socket.gaierror:
        return f"Refused: cannot resolve host {host}.", None
    if not ips:
        return f"Refused: cannot resolve host {host}.", None
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
            return f"Refused: {host} resolves to non-public address {ip_str}.", None
    return None, ips[0]


def ssrf_reason(url: str) -> str | None:
    """Refusal reason if the URL targets a non-public address, else None.

    Used as a standalone pre-flight check (e.g. for the Slack webhook URL).
    ``test_api_endpoint`` instead uses :func:`_check_and_pin` so the address it
    validates is the one it connects to.
    """
    host = urlparse(url).hostname
    if not host:
        return "Refused: no host in URL."
    reason, _ = _check_and_pin(host)
    return reason


def _pin_target(parsed: ParseResult, ip: str) -> tuple[str, str]:
    """Rewrite the URL to connect to ``ip`` and return the matching Host header.

    The hostname is replaced by the pinned IP (bracketed for IPv6) while the port
    and path are kept; the Host header carries the original hostname (with port,
    if any) so routing and name-based virtual hosts still work even though the
    connection targets the validated address.
    """
    literal = f"[{ip}]" if ":" in ip else ip
    netloc = f"{literal}:{parsed.port}" if parsed.port else literal
    target = parsed._replace(netloc=netloc).geturl()
    name = parsed.hostname or ""
    if ":" in name:  # IPv6 literal in the Host header
        name = f"[{name}]"
    host_header = f"{name}:{parsed.port}" if parsed.port else name
    return target, host_header


def _pinned_request(
    method: str, target: str, host_header: str, sni_hostname: str, timeout: int
) -> httpx.Response:
    """Send the request to the pinned-IP ``target`` as the original host.

    The Host header keeps name-based routing intact, and the ``sni_hostname``
    request extension makes the TLS handshake use the original hostname for both
    SNI and certificate verification — so connecting by IP does not weaken TLS.
    """
    with httpx.Client(timeout=timeout) as client:
        request = client.build_request(method, target, headers={"Host": host_header})
        request.extensions["sni_hostname"] = sni_hostname
        return client.send(request)


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
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return _fail("Refused: no host in URL.")
    reason, pinned_ip = _check_and_pin(host)
    if reason is not None or pinned_ip is None:
        return _fail(reason or f"Refused: cannot resolve host {host}.")
    target, host_header = _pin_target(parsed, pinned_ip)
    try:
        response = _pinned_request(method.upper(), target, host_header, host, timeout)
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
