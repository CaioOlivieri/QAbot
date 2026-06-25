"""Persistent defect ledger and run-over-run diff.

QAbot is otherwise one-shot: each run overwrites the report and forgets the
last one. This module keeps a per-target ledger at
``<project>/reports/qabot_state.json`` so defects can be *tracked* over time —
the foundation the professional report, CI gate and production reconciliation
all build on.

The diff/normalization helpers are pure functions (no I/O) so they can be
tested in isolation; ``record_run`` is the stateful entry point wired into the
agent.
"""

import json
import os
import statistics
import subprocess
import time

STATE_FILENAME = "qabot_state.json"
STATE_VERSION = 1


def _state_path(project_path: str) -> str:
    return os.path.join(project_path, "reports", STATE_FILENAME)


def _empty_state(project_path: str) -> dict[str, object]:
    return {
        "version": STATE_VERSION,
        "target": os.path.abspath(project_path),
        "runs": [],
    }


def load_state(project_path: str) -> dict[str, object]:
    """Read the ledger, falling back to a fresh one if missing or corrupt."""
    try:
        with open(_state_path(project_path)) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return _empty_state(project_path)
    if not isinstance(data, dict) or not isinstance(data.get("runs"), list):
        return _empty_state(project_path)
    return data


def save_state(project_path: str, state: dict[str, object]) -> str:
    """Persist the ledger as pretty, stable-ordered JSON; return its path."""
    path = _state_path(project_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
    return path


def fingerprint(finding: dict[str, object]) -> str:
    """Stable identity of a defect across runs: source, file, line, category."""
    return (
        f"{finding['source']}:{finding['file']}:{finding['line']}:{finding['category']}"
    )


def _normalize(source: str, category: str, bug: dict[str, object]) -> dict[str, object]:
    rec: dict[str, object] = {
        "source": source,
        "file": str(bug.get("file", "")),
        "line": int(bug.get("line") or 0),
        "category": str(category),
        "severity": str(bug.get("severity", "warning")),
        "description": str(bug.get("description", "")),
    }
    rec["fingerprint"] = fingerprint(rec)
    return rec


def extract_findings(
    ast_bugs: list[dict[str, object]],
    dynamic_bugs: list[dict[str, object]],
    suspected_bugs: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Flatten a run's confirmed defects into normalized ledger records.

    Static bugs keep their AST category; dynamic failures use their error type;
    only *confirmed* semantic suspicions are tracked (suspected/discarded are
    unverified and never scored).
    """
    findings: list[dict[str, object]] = []
    for bug in ast_bugs:
        findings.append(_normalize("static", str(bug.get("category", "static")), bug))
    for bug in dynamic_bugs:
        findings.append(
            _normalize("dynamic", str(bug.get("error_type", "failure")), bug)
        )
    for bug in suspected_bugs:
        if bug.get("status") == "confirmed":
            findings.append(_normalize("semantic", "semantic", bug))
    return findings


def diff_findings(
    previous: list[dict[str, object]],
    current: list[dict[str, object]],
    historical: set[str],
) -> dict[str, list[dict[str, object]]]:
    """Classify defects vs the previous run and the full history.

    - ``new``: never seen in any prior run.
    - ``regressed``: seen before, gone in the previous run, back now.
    - ``resolved``: present in the previous run, absent now.
    """
    prev_fps = {fingerprint(f) for f in previous}
    cur_fps = {fingerprint(f) for f in current}
    new = [f for f in current if fingerprint(f) not in historical]
    regressed = [
        f
        for f in current
        if fingerprint(f) in historical and fingerprint(f) not in prev_fps
    ]
    resolved = [f for f in previous if fingerprint(f) not in cur_fps]
    return {"new": new, "regressed": regressed, "resolved": resolved}


def diff_coverage(
    before: dict[str, float], after: dict[str, float]
) -> dict[str, float]:
    """Mean coverage of the previous vs current run, with the delta."""
    before_mean = statistics.mean(before.values()) if before else 0.0
    after_mean = statistics.mean(after.values()) if after else 0.0
    return {
        "before": before_mean,
        "after": after_mean,
        "delta": after_mean - before_mean,
    }


def _fmt_delta(delta: float) -> str:
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.1f}%"


def summarize_diff(diff: dict[str, object]) -> str:
    """One-line, human-readable summary of a run-over-run diff."""
    new = diff["new"]
    regressed = diff["regressed"]
    resolved = diff["resolved"]
    coverage = diff["coverage"]
    assert isinstance(new, list) and isinstance(regressed, list)
    assert isinstance(resolved, list) and isinstance(coverage, dict)
    return (
        f"Run-over-run: {len(new)} new, {len(regressed)} regressed, "
        f"{len(resolved)} resolved · coverage "
        f"{coverage['before']:.1f}% → {coverage['after']:.1f}% "
        f"({_fmt_delta(coverage['delta'])})"
    )


def current_commit(project_path: str) -> str | None:
    """Best-effort HEAD sha of the target; ``None`` if it is not a git repo."""
    try:
        result = subprocess.run(
            ["git", "-C", project_path, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def compute_diff(
    state: dict[str, object],
    ast_bugs: list[dict[str, object]],
    dynamic_bugs: list[dict[str, object]],
    suspected_bugs: list[dict[str, object]],
    coverage: dict[str, float],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Classify this run's findings against the ledger, *without* persisting.

    Pure read-over of ``state``: returns ``(current_findings, diff)`` where the
    diff carries ``new``/``regressed``/``resolved`` defect lists plus a
    ``coverage`` delta vs the previous run. ``record_run`` builds on it to
    append; the smoke CI gate uses it read-only so a pull request never writes
    the trend of the default branch.
    """
    runs = state["runs"]
    assert isinstance(runs, list)

    previous = list(runs[-1]["findings"]) if runs else []
    prev_coverage = dict(runs[-1]["coverage"]) if runs else {}
    historical = {fingerprint(f) for run in runs for f in run["findings"]}

    current = extract_findings(ast_bugs, dynamic_bugs, suspected_bugs)
    diff = diff_findings(previous, current, historical)
    diff["coverage"] = diff_coverage(prev_coverage, coverage)
    return current, diff


def record_run(
    project_path: str,
    ast_bugs: list[dict[str, object]],
    dynamic_bugs: list[dict[str, object]],
    suspected_bugs: list[dict[str, object]],
    coverage: dict[str, float],
    commit_sha: str | None = None,
    scores: dict[str, float] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    """Append this run to the ledger, persist it, and return ``(state, diff)``.

    The returned diff carries ``new``/``regressed``/``resolved`` defect lists
    plus a ``coverage`` delta vs the previous run.
    """
    state = load_state(project_path)
    current, diff = compute_diff(
        state, ast_bugs, dynamic_bugs, suspected_bugs, coverage
    )
    runs = state["runs"]
    assert isinstance(runs, list)

    new_fps = {fingerprint(f) for f in diff["new"]}
    regressed_fps = {fingerprint(f) for f in diff["regressed"]}
    for finding in current:
        if fingerprint(finding) in new_fps:
            finding["status"] = "new"
        elif fingerprint(finding) in regressed_fps:
            finding["status"] = "regressed"
        else:
            finding["status"] = "existing"

    runs.append(
        {
            "run_id": f"r{len(runs) + 1}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "commit_sha": commit_sha,
            "coverage": coverage,
            "scores": scores,
            "findings": current,
        }
    )
    save_state(project_path, state)
    return state, diff
