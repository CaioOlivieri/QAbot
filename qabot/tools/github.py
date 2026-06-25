"""GitHub issues adapter: production bugs for DRE reconciliation (Layer 3c).

Reads the target repo's GitHub issues (labeled bug/production) as the
production-bug source and normalizes them into ``reconcile.ProductionBug``.

Security: outbound egress to a FIXED, trusted host (``api.github.com``). The URL
is built from config, never from untrusted target content, so this is not an SSRF
surface. Opt-in — does nothing unless ``QABOT_PROD_REPO`` is set. Auth is optional
(public repos work unauthenticated but rate-limited); a read-only ``GITHUB_TOKEN``
raises the limit and reaches private repos. The token is read from the environment
only and is never logged or written.
"""

import os
import re

import httpx

from qabot.agent.reconcile import ProductionBug, extract_file_refs

_API = "https://api.github.com"
_NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')


def _config() -> dict[str, str] | None:
    repo = os.environ.get("QABOT_PROD_REPO", "").strip()
    if not repo:
        return None
    return {
        "repo": repo,
        "labels": os.environ.get("QABOT_PROD_LABELS", "bug,production").strip(),
        "token": os.environ.get("GITHUB_TOKEN", "").strip(),
    }


def _critical_labels() -> set[str]:
    raw = os.environ.get("QABOT_CRITICAL_LABELS", "critical,blocker,p0,sev1")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _classify_severity(labels: list[str], critical: set[str]) -> str:
    lowered = {label.lower() for label in labels}
    return "critical" if lowered & critical else "warning"


def _to_bug(issue: dict[str, object], critical: set[str]) -> ProductionBug:
    raw_labels = issue.get("labels", [])
    labels = [
        str(label.get("name", "")) if isinstance(label, dict) else str(label)
        for label in (raw_labels if isinstance(raw_labels, list) else [])
    ]
    text = f"{issue.get('title', '')}\n{issue.get('body') or ''}"
    return ProductionBug(
        number=int(issue.get("number", 0) or 0),
        severity=_classify_severity(labels, critical),
        file_refs=extract_file_refs(text),
        created_at=str(issue.get("created_at", "")),
    )


def _next_link(link_header: str) -> str | None:
    match = _NEXT_LINK.search(link_header)
    return match.group(1) if match else None


def fetch_production_bugs(
    timeout: int = 10, max_pages: int = 10
) -> list[ProductionBug] | None:
    """Fetch labeled issues as ``ProductionBug``s.

    Returns ``None`` when no source is configured (opt-in no-op); an empty list on a
    configured-but-failed/empty fetch, so the caller can tell 'no source' apart from
    'source returned nothing'.
    """
    config = _config()
    if config is None:
        return None

    headers = {"Accept": "application/vnd.github+json"}
    if config["token"]:
        headers["Authorization"] = f"Bearer {config['token']}"
    url: str | None = f"{_API}/repos/{config['repo']}/issues"
    params: dict[str, object] | None = {
        "labels": config["labels"],
        "state": "all",
        "per_page": 100,
    }
    critical = _critical_labels()
    bugs: list[ProductionBug] = []
    try:
        for _ in range(max_pages):
            response = httpx.get(url, headers=headers, params=params, timeout=timeout)
            response.raise_for_status()
            issues = response.json()
            bugs.extend(
                _to_bug(issue, critical)
                for issue in issues
                if "pull_request" not in issue
            )
            url = _next_link(response.headers.get("Link", ""))
            if not url:
                break
            params = None  # the next-page URL already carries the query
    except Exception as exc:
        print(f"Production reconciliation skipped: {type(exc).__name__}")
        return []
    return bugs
