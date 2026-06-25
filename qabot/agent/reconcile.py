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

    - ``flagged``: QAbot flagged a referenced file (caught, but shipped anyway).
    - ``undetected``: a file was referenced but QAbot never flagged it.
    - ``unmatched``: no code reference in the issue — cannot be attributed.
    """
    result: dict[str, list[ProductionBug]] = {
        "flagged": [],
        "undetected": [],
        "unmatched": [],
    }
    for bug in bugs:
        if not bug.file_refs:
            result["unmatched"].append(bug)
        elif any(ref in flagged_files for ref in bug.file_refs):
            result["flagged"].append(bug)
        else:
            result["undetected"].append(bug)
    return result
