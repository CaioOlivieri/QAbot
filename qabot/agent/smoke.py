"""Deterministic, LLM-free QA gate for CI pull-request runs.

The full agent (:func:`qabot.agent.core.run_agent`) generates and runs semantic
tests with an LLM — non-deterministic and secret-dependent, which makes it a
poor *blocking* PR check: GitHub withholds repository secrets from forked-PR
workflows, and a flaky required check is worse than none. The smoke tier is the
deterministic subset that *can* gate a pull request — static AST analysis plus
the project's existing test suite — scored and compared against the persisted
ledger, then run through the same PASS/FAIL gate as the full report.

This module never calls the LLM (it does not even import :mod:`qabot.agent.core`,
so it carries no ``google-genai`` dependency) and never mutates the ledger: a
pull request must not write the trend of the default branch. The scheduled
regression run owns generation and trend updates.
"""

import os
import time
from dataclasses import dataclass, field

from qabot import notify
from qabot.agent.exports import write_exports
from qabot.agent.report import (
    DEFAULT_THRESHOLDS,
    compute_scores,
    count_new_criticals,
    evaluate_gate,
    generate_report,
)
from qabot.state import compute_diff, current_commit, load_state, summarize_diff
from qabot.tools.analyzer import analyze_file_ast
from qabot.tools.fs import list_files
from qabot.tools.runner import parse_coverage, run_command

# The target's pytest config (addopts) is expected to wire ``--cov``; we only
# add the term report we parse. Override the whole command with QABOT_SMOKE_CMD.
DEFAULT_SMOKE_PYTEST = ["pytest", "-q", "--cov-report=term-missing"]

# Path segments that are never first-party source, skipped before AST analysis
# so a vendored dependency's bare-except can never trip the gate.
_SKIP_DIRS = frozenset(
    {".venv", "venv", "site-packages", "__pycache__", "node_modules", ".git"}
)


@dataclass
class SmokeResult:
    """Outcome of a smoke run: the gate verdict plus the rendered report."""

    verdict: str
    reasons: list[str]
    report_md: str
    coverage: dict[str, float] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.verdict == "PASS"


def _smoke_pytest_cmd() -> list[str]:
    override = os.environ.get("QABOT_SMOKE_CMD")
    if override:
        return override.split()
    return list(DEFAULT_SMOKE_PYTEST)


def _measure_coverage(project_path: str) -> dict[str, float]:
    """Run the existing suite and parse per-module coverage from its output."""
    _rc, stdout, stderr = run_command(_smoke_pytest_cmd(), cwd=project_path)
    return parse_coverage(f"{stdout}\n{stderr}")


def _source_ast_bugs(source_dir: str) -> list[dict[str, object]]:
    """AST findings over first-party source only (skips vendored/.venv dirs)."""
    bugs: list[dict[str, object]] = []
    for filepath in list_files(source_dir):
        if _SKIP_DIRS & set(filepath.split(os.sep)):
            continue
        bugs.extend(analyze_file_ast(filepath))
    return bugs


def _write_smoke_report(project_path: str, report_md: str) -> str:
    reports_dir = os.path.join(project_path, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, "qa_report.md")
    with open(report_path, "w") as f:
        f.write(report_md)
    return report_path


def run_smoke(project_path: str, source_dir: str | None = None) -> SmokeResult:
    """Run the deterministic gate: AST + existing suite + ledger diff + verdict.

    ``source_dir`` (default ``project_path``) bounds the AST scan to first-party
    code. The ledger is read but never written. The report and machine-readable
    exports are persisted under ``<project>/reports/`` for CI to upload; the
    returned :class:`SmokeResult` carries the verdict the CLI maps to an exit code.
    """
    source = source_dir or project_path
    ast_bugs = _source_ast_bugs(source)
    coverage = _measure_coverage(project_path)

    state = load_state(project_path)
    runs = state["runs"]
    assert isinstance(runs, list)

    _current, diff = compute_diff(state, ast_bugs, [], [], coverage)
    scores = compute_scores(coverage, ast_bugs, [], [], [])
    verdict, reasons = evaluate_gate(scores["coverage"], diff, DEFAULT_THRESHOLDS)

    previous_quality = (
        runs[-1]["scores"]["quality"]
        if runs and isinstance(runs[-1].get("scores"), dict)
        else None
    )
    # "Before" is the previous run's coverage so the report shows a real delta;
    # on the first run there is no baseline, so compare against itself (delta 0).
    coverage_before = dict(runs[-1]["coverage"]) if runs else coverage
    run_meta = {
        "run_id": f"smoke-{len(runs) + 1}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "commit_sha": current_commit(project_path),
        "thresholds": DEFAULT_THRESHOLDS,
    }
    report_md = generate_report(
        project_path,
        coverage_before,
        coverage,
        ast_bugs,
        [],
        [],
        [],
        diff=diff,
        run_meta=run_meta,
        previous_quality=previous_quality,
    )
    _write_smoke_report(project_path, report_md)
    write_exports(
        os.path.join(project_path, "reports"),
        coverage,
        ast_bugs,
        [],
        [],
        DEFAULT_THRESHOLDS,
    )
    print(summarize_diff(diff))
    notify.send(
        notify.Summary(
            project=project_path,
            verdict=verdict,
            reasons=reasons,
            quality=scores["quality"],
            previous_quality=previous_quality,
            new_criticals=count_new_criticals(diff),
            coverage=scores["coverage"],
        )
    )
    return SmokeResult(verdict, reasons, report_md, coverage)
