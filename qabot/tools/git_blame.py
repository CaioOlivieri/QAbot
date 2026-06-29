"""SZZ bug-introducing-commit provenance (opt-in, git-local, graceful).

The DRE escape rate counts a production bug as *catchable* only if QA had a real
chance to catch it. #46 used a time proxy (report time vs the first QA run). This
module provides the rigorous answer — the **SZZ algorithm** (Jacek Śliwerski,
Thomas Zimmermann & Andreas Zeller, "When Do Changes Induce Fixes?", MSR 2005):
given the commit that *fixed* a bug, blame that commit's changed lines on the
parent revision to locate the commit that *introduced* the defect, then ask
whether that commit is an ancestor of a commit QA analyzed — did the defective
code exist in a revision QA actually saw?

All work is on the LOCAL git repo at ``project_path`` (the analyzed target). The
fixing-commit sha comes from the production-bug source (GitHub), so provenance
only resolves when the two share history (e.g. dogfooding / the same repo). Every
git call is best-effort: any failure — not a git repo, a commit missing locally, a
root commit with no parent, a blame error — leaves the bug out of the result, and
the caller falls back to the #46 time-anchor. Escapes are never silently dropped.
"""

import re
import subprocess

from qabot.agent.reconcile import ProductionBug

_GIT_TIMEOUT = 10
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? ")
_BLAME_SHA = re.compile(r"^\^?([0-9a-f]{7,40})\s")


def _git(project_path: str, *args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["git", "-C", project_path, *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _ok(result: subprocess.CompletedProcess | None) -> bool:
    return result is not None and result.returncode == 0


def _commit_present(project_path: str, sha: str) -> bool:
    return bool(sha) and _ok(_git(project_path, "cat-file", "-e", f"{sha}^{{commit}}"))


def _changed_py_ranges(
    project_path: str, fix_sha: str
) -> dict[str, list[tuple[int, int]]]:
    """Pre-image line ranges, per ``.py`` file, of the lines the fix changed.

    ``--unified=0`` makes each hunk header (``@@ -a,b +c,d @@``) name exactly the
    parent-side lines the fix deleted/modified — the lines to blame on the parent.
    Pure additions (``b == 0``) introduce no prior line and are skipped.
    """
    result = _git(project_path, "show", "--unified=0", "--format=", fix_sha)
    if not _ok(result):
        return {}
    assert result is not None
    ranges: dict[str, list[tuple[int, int]]] = {}
    current: str | None = None
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            path = line[len("+++ b/") :]
            current = path if path.endswith(".py") else None
        elif current and line.startswith("@@"):
            match = _HUNK.match(line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2)) if match.group(2) is not None else 1
                if count > 0:
                    ranges.setdefault(current, []).append((start, start + count - 1))
    return ranges


def _blame_introducers(
    project_path: str, parent: str, path: str, ranges: list[tuple[int, int]]
) -> set[str]:
    shas: set[str] = set()
    for start, end in ranges:
        result = _git(
            project_path, "blame", "-l", "-L", f"{start},{end}", parent, "--", path
        )
        if not _ok(result):
            continue
        assert result is not None
        for line in result.stdout.splitlines():
            match = _BLAME_SHA.match(line)
            if match:
                shas.add(match.group(1))
    return shas


def introducing_commits(project_path: str, fix_sha: str) -> set[str]:
    """SZZ candidate bug-introducing commits for ``fix_sha``; empty on failure."""
    if not _commit_present(project_path, fix_sha):
        return set()
    ranges = _changed_py_ranges(project_path, fix_sha)
    if not ranges:
        return set()
    parent = f"{fix_sha}^"
    shas: set[str] = set()
    for path, line_ranges in ranges.items():
        shas |= _blame_introducers(project_path, parent, path, line_ranges)
    return shas


def _is_ancestor(project_path: str, ancestor: str, descendant: str) -> bool:
    return _ok(_git(project_path, "merge-base", "--is-ancestor", ancestor, descendant))


def resolve_provenance(
    project_path: str, bugs: list[ProductionBug], qa_shas: list[str]
) -> dict[int, bool]:
    """Map each *resolvable* bug number to whether its introducing commit is
    reachable from a QA-analyzed commit.

    A bug whose fixing commit, changed lines, or blame cannot be resolved locally
    is **omitted** from the result, so the caller falls back to the time-anchor
    for it. Returns an empty map (full fallback) when no QA commit is present in
    the local history — the common cross-repo case.
    """
    present_qa = [sha for sha in qa_shas if _commit_present(project_path, sha)]
    if not present_qa:
        return {}
    provenance: dict[int, bool] = {}
    for bug in bugs:
        introducers = introducing_commits(project_path, bug.fix_commit_sha)
        if not introducers:
            continue
        provenance[bug.number] = any(
            _is_ancestor(project_path, intro, qa)
            for intro in introducers
            for qa in present_qa
        )
    return provenance
