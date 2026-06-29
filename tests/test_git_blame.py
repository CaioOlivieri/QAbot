import subprocess

from qabot.agent.reconcile import ProductionBug
from qabot.tools import git_blame


def _git(repo, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _commit(repo, message: str) -> str:
    _git(repo, "add", "-A")
    _git(
        repo,
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        "commit",
        "-q",
        "-m",
        message,
    )
    return _git(repo, "rev-parse", "HEAD")


def _build_repo(tmp_path) -> dict:
    """A repo where c1 introduces a bug, c2 is a later (QA-analyzed) commit, and
    c3 fixes the bug. Blaming c3's change should point back to c1.

        c0 (clean) -> c1 (bug) -> c2 (unrelated) -> c3 (fix)
    """
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    ops = repo / "ops.py"
    ops.write_text("def f():\n    return 1\n")
    c0 = _commit(repo, "c0 clean")
    ops.write_text("def f():\n    return 2  # bug\n")
    c1 = _commit(repo, "c1 introduce bug")
    (repo / "other.txt").write_text("x\n")
    c2 = _commit(repo, "c2 unrelated")
    ops.write_text("def f():\n    return 1\n")
    c3 = _commit(repo, "c3 fix")
    return {"repo": repo, "c0": c0, "c1": c1, "c2": c2, "c3": c3}


def _bug(fix_sha: str, number: int = 1) -> ProductionBug:
    return ProductionBug(
        number=number,
        severity="critical",
        file_refs=(),
        created_at="2020-01-01T00:00:00Z",
        fix_commit_sha=fix_sha,
    )


def test_introducing_commits_finds_the_bug_commit(tmp_path) -> None:
    r = _build_repo(tmp_path)
    introducers = git_blame.introducing_commits(str(r["repo"]), r["c3"])
    assert r["c1"] in introducers


def test_resolve_provenance_reachable_when_qa_saw_the_bug(tmp_path) -> None:
    r = _build_repo(tmp_path)
    # QA analyzed c2, whose history already contained the buggy c1.
    prov = git_blame.resolve_provenance(str(r["repo"]), [_bug(r["c3"])], [r["c2"]])
    assert prov == {1: True}


def test_resolve_provenance_not_reachable_when_qa_predates_bug(tmp_path) -> None:
    r = _build_repo(tmp_path)
    # QA analyzed c0, before the bug existed → not its to catch.
    prov = git_blame.resolve_provenance(str(r["repo"]), [_bug(r["c3"])], [r["c0"]])
    assert prov == {1: False}


def test_resolve_provenance_empty_when_no_qa_commit_local(tmp_path) -> None:
    r = _build_repo(tmp_path)
    prov = git_blame.resolve_provenance(str(r["repo"]), [_bug(r["c3"])], ["0" * 40])
    assert prov == {}  # nothing anchorable → caller falls back entirely


def test_resolve_provenance_omits_bug_with_no_fix_sha(tmp_path) -> None:
    r = _build_repo(tmp_path)
    prov = git_blame.resolve_provenance(str(r["repo"]), [_bug("")], [r["c2"]])
    assert prov == {}  # unresolvable → omitted, caller falls back for it


def test_introducing_commits_graceful_on_non_git_dir(tmp_path) -> None:
    assert git_blame.introducing_commits(str(tmp_path), "deadbeef") == set()


class _Result:
    """Minimal stand-in for subprocess.CompletedProcess."""

    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


def test_introducing_commits_graceful_when_show_fails(monkeypatch) -> None:
    def fake_git(project_path, *args):
        return _Result(0) if args[0] == "cat-file" else _Result(1)

    monkeypatch.setattr(git_blame, "_git", fake_git)
    # commit present, but `git show` fails → no ranges → empty (degrades cleanly)
    assert git_blame.introducing_commits("x", "deadbeef") == set()


def test_introducing_commits_graceful_when_blame_fails(monkeypatch) -> None:
    def fake_git(project_path, *args):
        if args[0] == "cat-file":
            return _Result(0)
        if args[0] == "show":
            return _Result(0, "+++ b/ops.py\n@@ -2,1 +2,1 @@\n")
        return _Result(1)  # blame fails

    monkeypatch.setattr(git_blame, "_git", fake_git)
    assert git_blame.introducing_commits("x", "deadbeef") == set()


def test_git_graceful_on_os_error(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise OSError("git not found")

    monkeypatch.setattr(git_blame.subprocess, "run", boom)
    assert git_blame.introducing_commits("x", "deadbeef") == set()
