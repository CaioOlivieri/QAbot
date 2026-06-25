"""Deliver the gate verdict where the dev team works: Slack + a GitHub PR comment.

QAbot otherwise only writes a report file. This posts a concise summary — quality
score + trend, gate verdict, new criticals, critical escape rate, and a link — to a
Slack incoming webhook and as a single (upserted) GitHub pull-request comment.

Both channels are **opt-in by configuration presence** and a silent no-op when
unset, so the CLI-only flow is unchanged. Egress here is operator-configured (your
webhook, ``api.github.com``) — distinct from the agent's API testing, which targets
untrusted URLs scraped from the project and stays behind ``QABOT_ALLOW_NETWORK`` +
the SSRF guard. As defence in depth the same ``ssrf_reason`` check is applied to the
Slack webhook URL before posting.
"""

import json
import os
from dataclasses import dataclass, field

import httpx

from qabot.tools.api import ssrf_reason

_HTTP_TIMEOUT = 10
_COMMENT_MARKER = "<!-- qabot-summary -->"


@dataclass
class Summary:
    """The data sent to every channel; assembled by the run that produced it."""

    project: str
    verdict: str
    reasons: list[str] = field(default_factory=list)
    quality: float = 0.0
    previous_quality: float | None = None
    new_criticals: int = 0
    coverage: float = 0.0
    escape_rate: float | None = None
    report_url: str | None = None


def _display_name(project: str) -> str:
    """A readable project label: the directory name, not the raw path.

    Turns ``"."`` into the current directory's name (e.g. ``QAbot``) and
    ``~/Projetos/qabot_target`` into ``qabot_target``.
    """
    return os.path.basename(os.path.abspath(project)) or project


def _trend(quality: float, previous: float | None) -> str:
    if previous is None:
        return "(first run)"
    delta = quality - previous
    if delta > 0.05:
        return f"▲ +{delta:.1f}"
    if delta < -0.05:
        return f"▼ {delta:.1f}"
    return "▬ no change"


def format_summary(summary: Summary) -> str:
    """Markdown summary shared by Slack and the GitHub comment."""
    icon = "✅" if summary.verdict == "PASS" else "❌"
    gate = f"{icon} **Gate: {summary.verdict}**"
    if summary.reasons:
        gate += f" — {'; '.join(summary.reasons)}"
    lines = [
        f"**QAbot — {_display_name(summary.project)}**",
        gate,
        f"Quality {summary.quality:.1f}/100 "
        f"{_trend(summary.quality, summary.previous_quality)} · "
        f"Coverage {summary.coverage:.1f}% · New criticals {summary.new_criticals}",
    ]
    if summary.escape_rate is not None:
        lines.append(f"Critical escape rate {summary.escape_rate:.1f}%")
    if summary.report_url:
        lines.append(f"[Full report]({summary.report_url})")
    return "\n".join(lines)


def notify_slack(summary: Summary) -> bool:
    """Post to the Slack incoming webhook if SLACK_WEBHOOK_URL is set; else no-op."""
    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        return False
    reason = ssrf_reason(url)
    if reason is not None:
        print(f"Slack notify skipped: {reason}")
        return False
    try:
        httpx.post(url, json={"text": format_summary(summary)}, timeout=_HTTP_TIMEOUT)
        return True
    except Exception as exc:
        print(f"Slack notify failed: {exc}")
        return False


def _pr_number() -> int | None:
    """The PR number from the GitHub Actions event payload, if this is a PR run."""
    path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            event = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    pr = event.get("pull_request")
    if isinstance(pr, dict) and isinstance(pr.get("number"), int):
        return pr["number"]
    return None


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def notify_github_pr(summary: Summary) -> bool:
    """Upsert a single QAbot comment on the current PR; no-op outside a PR run.

    Needs GITHUB_TOKEN (with pull-requests:write) and the Actions PR context. On
    fork PRs the token is read-only, so the post fails gracefully (logged, no raise).
    """
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    number = _pr_number()
    if not token or not repo or number is None:
        return False
    body = f"{_COMMENT_MARKER}\n{format_summary(summary)}"
    headers = _github_headers(token)
    try:
        existing = httpx.get(
            f"{api}/repos/{repo}/issues/{number}/comments",
            headers=headers,
            timeout=_HTTP_TIMEOUT,
        )
        comment_id: int | None = None
        if existing.status_code == 200:
            for comment in existing.json():
                if _COMMENT_MARKER in (comment.get("body") or ""):
                    comment_id = comment.get("id")
                    break
        if comment_id is not None:
            httpx.patch(
                f"{api}/repos/{repo}/issues/comments/{comment_id}",
                headers=headers,
                json={"body": body},
                timeout=_HTTP_TIMEOUT,
            )
        else:
            httpx.post(
                f"{api}/repos/{repo}/issues/{number}/comments",
                headers=headers,
                json={"body": body},
                timeout=_HTTP_TIMEOUT,
            )
        return True
    except Exception as exc:
        print(f"GitHub PR comment failed: {exc}")
        return False


def _report_url() -> str | None:
    """Link to the Actions run page, when running inside GitHub Actions."""
    server = os.environ.get("GITHUB_SERVER_URL", "").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return None


def send(summary: Summary) -> None:
    """Fan out to every configured channel; each is a no-op when unconfigured."""
    if summary.report_url is None:
        summary.report_url = _report_url()
    notify_slack(summary)
    notify_github_pr(summary)
