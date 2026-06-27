"""Defect escape rate / DRE reconciliation (Layer 3c).

Defect Removal Efficiency (DRE) and its inverse, the defect escape rate, are
*counting* metrics: a defect found in production is an **escape by definition**
(Capers Jones, "The Economics of Software Quality", 2011 — DRE originated at IBM
~1973; DRE = internal / (internal + external), measured over a window — Jones uses
90 days, ISBSG 30).

So the headline (critical escape rate) needs no fuzzy matching — only counts.
``detection_breakdown`` is a *secondary* diagnostic: of the escaped production
bugs, did QAbot already flag the referenced file (via a stack trace in the issue)?
It splits them into flagged-but-shipped / undetected / unmatched.

Pure module: no I/O, no network. The GitHub adapter builds ``ProductionBug``s; the
agent supplies the QA counts from the ledger.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

DEFAULT_DRE_WINDOW_DAYS = 90  # Capers Jones; ISBSG uses 30.

_TRACEBACK = re.compile(r'File "([^"]+\.py)", line \d+')
_PATH_REF = re.compile(r"[\w./\\-]+\.py")


@dataclass(frozen=True)
class ProductionBug:
    number: int
    severity: str
    file_refs: tuple[str, ...]
    created_at: str  # ISO 8601
    # Basenames of files changed by the commit that *fixed* this bug (resolved
    # from the issue's "closed by" event). A second attribution signal, used
    # when the issue text carries no stack trace; empty when none was resolved.
    fix_file_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class EscapeRate:
    caught: int
    escaped: int
    escape_rate: float | None  # percent; None when there are no defects at all
    dre: float | None


def _basename(path: str) -> str:
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def extract_file_refs(text: str) -> tuple[str, ...]:
    """Python file basenames referenced in issue text (stack traces / paths)."""
    refs: set[str] = set()
    for match in _TRACEBACK.finditer(text):
        refs.add(_basename(match.group(1)))
    for match in _PATH_REF.finditer(text):
        refs.add(_basename(match.group(0)))
    return tuple(sorted(refs))


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def within_window(
    bugs: list[ProductionBug], window_days: int, reference_iso: str
) -> list[ProductionBug]:
    """Bugs reported within ``window_days`` before the reference time."""
    cutoff = _parse_time(reference_iso) - timedelta(days=window_days)
    return [bug for bug in bugs if _parse_time(bug.created_at) >= cutoff]


def count_critical(bugs: list[ProductionBug]) -> int:
    return sum(1 for bug in bugs if bug.severity == "critical")


def qa_observation_start(runs: list[dict[str, object]]) -> str | None:
    """Earliest run timestamp at which QA analyzed a known commit, or ``None``.

    Temporal-anchoring reference: a production bug reported *before* QA ever ran
    on a recorded commit was never QA's to catch, so counting it as an "escape"
    overstates the rate. Returns ``None`` when no run carries a ``commit_sha``,
    in which case anchoring is skipped (see :func:`catchable`).
    """
    observed = [
        str(run["timestamp"])
        for run in runs
        if run.get("commit_sha") and run.get("timestamp")
    ]
    return min(observed) if observed else None


def catchable(bugs: list[ProductionBug], anchor_iso: str | None) -> list[ProductionBug]:
    """Bugs QA had a real chance to catch: reported at/after it began observing.

    This is a deliberately lightweight, time-based proxy for *defect provenance*
    — "did the defective code exist in a revision QA actually analyzed?". The
    rigorous answer is commit-level provenance: identify the bug-introducing
    commit and check it against the analyzed history. That is the **SZZ
    algorithm** (Jacek Śliwerski, Thomas Zimmermann & Andreas Zeller, "When Do
    Changes Induce Fixes?", MSR 2005), which blames the fixing commit's changed
    lines to locate the change that introduced the defect. SZZ needs full git
    history and line-level blame, so we approximate it here with the issue's
    report time against the first observed run; the SZZ-based version is tracked
    as a follow-up. When ``anchor_iso`` is ``None`` we cannot anchor and return
    all bugs unchanged, so escapes are never silently dropped.
    """
    if anchor_iso is None:
        return list(bugs)
    cutoff = _parse_time(anchor_iso)
    return [bug for bug in bugs if _parse_time(bug.created_at) >= cutoff]


def escape_rate(caught: int, escaped: int) -> EscapeRate:
    """Escape rate (escaped / total) and DRE (caught / total), as percentages."""
    total = caught + escaped
    if total == 0:
        return EscapeRate(caught, escaped, None, None)
    return EscapeRate(caught, escaped, escaped / total * 100.0, caught / total * 100.0)


def detection_breakdown(
    bugs: list[ProductionBug], flagged_files: set[str]
) -> dict[str, list[ProductionBug]]:
    """Split production bugs by whether QAbot had flagged the referenced file.

    A bug is attributed to a file via two signals: references parsed from the
    issue text (stack traces) and, as a fallback, the files changed by its
    fixing commit (``fix_file_refs``). The fix-commit signal rescues bugs that
    have no stack trace from the ``unmatched`` bucket.

    - ``flagged``: QAbot flagged a referenced file (caught, but shipped anyway).
    - ``undetected``: a file was referenced but QAbot never flagged it.
    - ``unmatched``: no code reference at all — cannot be attributed.
    """
    result: dict[str, list[ProductionBug]] = {
        "flagged": [],
        "undetected": [],
        "unmatched": [],
    }
    for bug in bugs:
        candidates = bug.file_refs + bug.fix_file_refs
        if not candidates:
            result["unmatched"].append(bug)
        elif any(ref in flagged_files for ref in candidates):
            result["flagged"].append(bug)
        else:
            result["undetected"].append(bug)
    return result
