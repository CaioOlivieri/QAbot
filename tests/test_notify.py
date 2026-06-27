import json
from unittest.mock import patch

import qabot.notify as notify


def _summary(verdict="PASS", reasons=None, escape_rate=None):
    return notify.Summary(
        project="proj",
        verdict=verdict,
        reasons=reasons or [],
        quality=90.0,
        previous_quality=85.0,
        new_criticals=0,
        coverage=95.0,
        escape_rate=escape_rate,
    )


def test_display_name_strips_path_to_basename():
    assert notify._display_name("/home/user/qabot_target") == "qabot_target"
    assert notify._display_name(".") != "."  # resolves to the cwd's name


def test_format_summary_pass_has_key_fields():
    text = notify.format_summary(_summary())
    assert "Gate: PASS" in text
    assert "Quality 90.0/100" in text
    assert "▲ +5.0" in text  # trend vs previous 85.0
    assert "Coverage 95.0%" in text


def test_format_summary_fail_lists_reasons_and_escape():
    text = notify.format_summary(
        _summary("FAIL", ["coverage 50.0% ≤ 80%"], escape_rate=88.0)
    )
    assert "Gate: FAIL" in text
    assert "coverage 50.0%" in text
    assert "Critical escape rate 88.0%" in text


def test_format_trend_first_run_and_no_change():
    first = notify.Summary(project="p", verdict="PASS", quality=90.0)
    assert "(first run)" in notify.format_summary(first)
    flat = notify.Summary(
        project="p", verdict="PASS", quality=90.0, previous_quality=90.0
    )
    assert "no change" in notify.format_summary(flat)


def test_format_trend_down_shows_decline():
    dropped = notify.Summary(
        project="p", verdict="FAIL", quality=80.0, previous_quality=90.0
    )
    assert "▼ -10.0" in notify.format_summary(dropped)


def test_format_summary_includes_report_link_when_present():
    summary = _summary()
    summary.report_url = "https://github.com/owner/repo/actions/runs/123"
    text = notify.format_summary(summary)
    assert "[Full report](https://github.com/owner/repo/actions/runs/123)" in text


def test_slack_handles_http_exception(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/x")
    with (
        patch.object(notify, "ssrf_reason", return_value=None),
        patch.object(notify, "httpx") as mock_httpx,
    ):
        mock_httpx.post.side_effect = RuntimeError("boom")
        assert notify.notify_slack(_summary()) is False


def test_send_sets_report_url_from_actions_env(monkeypatch):
    for var in ("SLACK_WEBHOOK_URL", "GITHUB_TOKEN", "GITHUB_EVENT_PATH"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    summary = _summary()
    with patch.object(notify, "httpx"):
        notify.send(summary)
    assert summary.report_url == "https://github.com/owner/repo/actions/runs/123"


def test_slack_noop_when_unset(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    with patch.object(notify, "httpx") as mock_httpx:
        assert notify.notify_slack(_summary()) is False
    mock_httpx.post.assert_not_called()


def test_slack_posts_when_configured(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/x")
    with (
        patch.object(notify, "ssrf_reason", return_value=None),
        patch.object(notify, "httpx") as mock_httpx,
    ):
        assert notify.notify_slack(_summary()) is True
    mock_httpx.post.assert_called_once()
    assert "Gate: PASS" in mock_httpx.post.call_args.kwargs["json"]["text"]


def test_slack_refuses_non_public_url(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "http://169.254.169.254/")
    with (
        patch.object(notify, "ssrf_reason", return_value="Refused: non-public"),
        patch.object(notify, "httpx") as mock_httpx,
    ):
        assert notify.notify_slack(_summary()) is False
    mock_httpx.post.assert_not_called()


def test_pr_number_from_event_payload(tmp_path, monkeypatch):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 7}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    assert notify._pr_number() == 7


def test_github_noop_without_context(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    with patch.object(notify, "httpx") as mock_httpx:
        assert notify.notify_github_pr(_summary()) is False
    mock_httpx.get.assert_not_called()


def _pr_env(tmp_path, monkeypatch):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 7}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_TOKEN", "t0ken")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_API_URL", "https://api.github.com")


def test_github_posts_new_comment(tmp_path, monkeypatch):
    _pr_env(tmp_path, monkeypatch)
    with patch.object(notify, "httpx") as mock_httpx:
        mock_httpx.get.return_value.status_code = 200
        mock_httpx.get.return_value.json.return_value = []
        assert notify.notify_github_pr(_summary()) is True
    mock_httpx.post.assert_called_once()
    mock_httpx.patch.assert_not_called()
    assert mock_httpx.post.call_args.args[0].endswith(
        "/repos/owner/repo/issues/7/comments"
    )


def test_github_upserts_existing_comment(tmp_path, monkeypatch):
    _pr_env(tmp_path, monkeypatch)
    with patch.object(notify, "httpx") as mock_httpx:
        mock_httpx.get.return_value.status_code = 200
        mock_httpx.get.return_value.json.return_value = [
            {"id": 99, "body": f"{notify._COMMENT_MARKER}\nold summary"}
        ]
        assert notify.notify_github_pr(_summary()) is True
    mock_httpx.patch.assert_called_once()
    mock_httpx.post.assert_not_called()
    assert mock_httpx.patch.call_args.args[0].endswith(
        "/repos/owner/repo/issues/comments/99"
    )


def test_send_is_silent_noop_when_unconfigured(monkeypatch):
    for var in ("SLACK_WEBHOOK_URL", "GITHUB_TOKEN", "GITHUB_EVENT_PATH"):
        monkeypatch.delenv(var, raising=False)
    with patch.object(notify, "httpx") as mock_httpx:
        notify.send(_summary())  # must not raise
    mock_httpx.post.assert_not_called()
    mock_httpx.get.assert_not_called()


def test_pr_number_none_on_malformed_or_missing(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json")  # JSONDecodeError -> None
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(bad))
    assert notify._pr_number() is None

    push = tmp_path / "push.json"
    push.write_text(json.dumps({"ref": "refs/heads/main"}))  # no pull_request -> None
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(push))
    assert notify._pr_number() is None


def test_github_handles_http_exception(tmp_path, monkeypatch):
    _pr_env(tmp_path, monkeypatch)
    with patch.object(notify, "httpx") as mock_httpx:
        mock_httpx.get.side_effect = RuntimeError("boom")
        assert notify.notify_github_pr(_summary()) is False
