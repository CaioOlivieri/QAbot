from unittest.mock import MagicMock, patch

from qabot.tools import github


def _resp(json_data: list[dict], link: str = "") -> MagicMock:
    response = MagicMock()
    response.json.return_value = json_data
    response.headers = {"Link": link}
    response.raise_for_status = MagicMock()
    return response


def _issue(number: int, **extra: object) -> dict[str, object]:
    base: dict[str, object] = {
        "number": number,
        "title": "t",
        "body": "",
        "labels": [],
        "created_at": "2026-06-20T00:00:00Z",
    }
    base.update(extra)
    return base


def test_no_op_when_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("QABOT_PROD_REPO", raising=False)
    assert github.fetch_production_bugs() is None


def test_fetches_normalizes_and_skips_prs(monkeypatch) -> None:
    monkeypatch.setenv("QABOT_PROD_REPO", "owner/repo")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    issues = [
        _issue(
            1,
            body='Traceback:\n  File "ops.py", line 3, in run',
            labels=[{"name": "bug"}, {"name": "critical"}],
        ),
        _issue(2, pull_request={"url": "x"}),
    ]
    with patch("qabot.tools.github.httpx.get", return_value=_resp(issues)) as get:
        bugs = github.fetch_production_bugs()
    assert [b.number for b in bugs] == [1]  # the PR is skipped
    assert bugs[0].severity == "critical"
    assert bugs[0].file_refs == ("ops.py",)
    assert "Authorization" not in get.call_args.kwargs["headers"]


def test_token_sets_auth_header(monkeypatch) -> None:
    monkeypatch.setenv("QABOT_PROD_REPO", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "fake-test-token")
    with patch("qabot.tools.github.httpx.get", return_value=_resp([])) as get:
        github.fetch_production_bugs()
    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer fake-test-token"


def test_failure_returns_empty_list(monkeypatch) -> None:
    monkeypatch.setenv("QABOT_PROD_REPO", "owner/repo")
    with patch("qabot.tools.github.httpx.get", side_effect=Exception("boom")):
        assert github.fetch_production_bugs() == []


def test_follows_pagination(monkeypatch) -> None:
    monkeypatch.setenv("QABOT_PROD_REPO", "owner/repo")
    page1 = _resp([_issue(1)], link='<https://api.github.com/x?page=2>; rel="next"')
    page2 = _resp([_issue(2)])
    with patch("qabot.tools.github.httpx.get", side_effect=[page1, page2]) as get:
        bugs = github.fetch_production_bugs()
    assert [b.number for b in bugs] == [1, 2]
    assert get.call_count == 2


def test_enriches_with_fix_commit_when_no_text_ref(monkeypatch) -> None:
    monkeypatch.setenv("QABOT_PROD_REPO", "owner/repo")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    issues = _resp([_issue(7, state="closed", labels=[{"name": "critical"}])])
    timeline = _resp([{"event": "labeled"}, {"event": "closed", "commit_id": "sha1"}])
    commit = _resp(
        {"files": [{"filename": "qabot/agent/core.py"}, {"filename": "README.md"}]}
    )
    with patch(
        "qabot.tools.github.httpx.get", side_effect=[issues, timeline, commit]
    ) as get:
        bugs = github.fetch_production_bugs()
    assert bugs[0].fix_file_refs == ("core.py",)  # non-.py file filtered out
    assert bugs[0].fix_commit_sha == "sha1"  # SZZ provenance entry point
    assert get.call_count == 3  # issues + timeline + commit


def test_fix_lookup_graceful_when_no_closing_commit(monkeypatch) -> None:
    monkeypatch.setenv("QABOT_PROD_REPO", "owner/repo")
    issues = _resp([_issue(7, state="closed", labels=[{"name": "critical"}])])
    timeline = _resp([{"event": "labeled"}])  # no closed-by-commit event
    with patch("qabot.tools.github.httpx.get", side_effect=[issues, timeline]) as get:
        bugs = github.fetch_production_bugs()
    assert bugs[0].fix_file_refs == ()  # falls back, no crash
    assert get.call_count == 2  # no commit fetch without a sha


def test_fix_lookup_graceful_on_api_error(monkeypatch) -> None:
    monkeypatch.setenv("QABOT_PROD_REPO", "owner/repo")
    issues = _resp([_issue(7, state="closed", labels=[{"name": "critical"}])])
    # The issues list returns, then the timeline call raises.
    with patch(
        "qabot.tools.github.httpx.get", side_effect=[issues, Exception("boom")]
    ) as get:
        bugs = github.fetch_production_bugs()
    assert bugs[0].fix_file_refs == ()  # swallowed, fetch still succeeds
    assert get.call_count == 2


def test_fix_lookup_runs_even_with_text_ref_for_szz_sha(monkeypatch) -> None:
    # A stack trace already attributes the bug, but SZZ provenance still needs
    # the fixing-commit sha, so the lookup runs for any critical closed bug.
    monkeypatch.setenv("QABOT_PROD_REPO", "owner/repo")
    issues = _resp(
        [
            _issue(
                7,
                state="closed",
                body='File "ops.py", line 1',
                labels=[{"name": "critical"}],
            )
        ]
    )
    timeline = _resp([{"event": "closed", "commit_id": "sha9"}])
    commit = _resp({"files": [{"filename": "ops.py"}]})
    with patch(
        "qabot.tools.github.httpx.get", side_effect=[issues, timeline, commit]
    ) as get:
        bugs = github.fetch_production_bugs()
    assert bugs[0].file_refs == ("ops.py",)  # text ref preserved
    assert bugs[0].fix_commit_sha == "sha9"  # sha captured for SZZ
    assert get.call_count == 3
