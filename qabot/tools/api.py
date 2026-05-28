import glob
import os
import re

import httpx


def detect_api_endpoints(project_path: str) -> list[str]:
    urls: set[str] = set()
    pattern = re.compile(r"https?://[^\s\"'`\)]+")
    for filepath in glob.glob(os.path.join(project_path, "**/*.py"), recursive=True):
        with open(filepath) as f:
            content = f.read()
        urls.update(url.rstrip(".,;:)]}\"'`") for url in pattern.findall(content))
    return sorted(urls)


def test_api_endpoint(
    url: str,
    method: str = "GET",
    expected_status: int = 200,
    timeout: int = 10,
) -> dict[str, str | int | bool]:
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
        return {
            "url": url,
            "method": method.upper(),
            "status_code": 0,
            "expected_status": expected_status,
            "passed": False,
            "error": str(e),
        }
