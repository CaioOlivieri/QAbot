import statistics


def _section_coverage(
    before: dict[str, float],
    after: dict[str, float],
) -> str:
    lines: list[str] = [
        "## Coverage",
        "",
        "| Module | Before | After | Δ |",
        "| --- | --- | --- | --- |",
    ]
    all_keys: list[str] = sorted(set(before) | set(after))
    rows: list[tuple[float, str]] = []
    for k in all_keys:
        b = before.get(k, 0.0)
        a = after.get(k, 0.0)
        delta = a - b
        rows.append((delta, f"| {k} | {b:.1f}% | {a:.1f}% | {_fmt_delta(delta)} |"))
    rows.sort(key=lambda r: r[0])
    lines.extend(r[1] for r in rows)
    return "\n".join(lines)


def _fmt_delta(delta: float) -> str:
    if delta == 0.0:
        return "—"
    sign = "+" if delta > 0 else ""
    return f"{sign}{delta:.1f}%"


def _by_severity(bug: dict[str, object]) -> tuple[int, object, object]:
    return (0 if bug["severity"] == "critical" else 1, bug["file"], bug["line"])


def _section_ast_bugs(bugs: list[dict[str, object]]) -> str:
    lines: list[str] = [
        "## Static Bugs (AST)",
        "",
        "| File | Line | Severity | Category | Description |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not bugs:
        lines.append("No static bugs found.")
        return "\n".join(lines)
    sorted_bugs = sorted(bugs, key=_by_severity)
    for b in sorted_bugs:
        lines.append(
            f"| {b['file']} | {b['line']} | {b['severity']} | "
            f"{b['category']} | {b['description']} |"
        )
    return "\n".join(lines)


def _section_dynamic_bugs(bugs: list[dict[str, object]]) -> str:
    lines: list[str] = [
        "## Dynamic Bugs (pytest)",
        "",
        "| File | Line | Test | Severity | Error Type | Description |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if not bugs:
        lines.append("No dynamic bugs found.")
        return "\n".join(lines)
    sorted_bugs = sorted(bugs, key=_by_severity)
    for b in sorted_bugs:
        lines.append(
            f"| {b['file']} | {b['line']} | {b['test_name']} | {b['severity']} | "
            f"{b['error_type']} | {b['description']} |"
        )
    return "\n".join(lines)


def _section_api(results: list[dict[str, object]]) -> str:
    lines: list[str] = [
        "## API Testing",
        "",
        "| URL | Method | Expected | Got | Result |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not results:
        lines.append("No API endpoints tested.")
        return "\n".join(lines)
    for r in results:
        url = r.get("url", "")
        method = r.get("method", "")
        expected = str(r.get("expected_status", ""))
        got = str(r.get("status_code", ""))
        if r.get("passed"):
            result_text = "✓ passed"
        elif r.get("error"):
            result_text = "✗ failed (error)"
        else:
            result_text = "✗ failed"
        lines.append(f"| {url} | {method} | {expected} | {got} | {result_text} |")
    return "\n".join(lines)


def _section_suspicions(
    suspected_bugs: list[dict[str, object]],
    status: str,
    title: str,
    empty: str,
) -> str:
    matching = [b for b in suspected_bugs if b.get("status") == status]
    lines: list[str] = [
        title,
        "",
        "| File | Line | Severity | Description |",
        "| --- | --- | --- | --- |",
    ]
    if not matching:
        lines.append(empty)
        return "\n".join(lines)
    for b in sorted(matching, key=lambda b: (b["file"], b["line"])):
        lines.append(
            f"| {b['file']} | {b['line']} | {b['severity']} | {b['description']} |"
        )
    return "\n".join(lines)


def _section_semantic_bugs(suspected_bugs: list[dict[str, object]]) -> str:
    return _section_suspicions(
        suspected_bugs,
        "confirmed",
        "## Semantic Bugs (LLM, confirmed by execution)",
        "No confirmed semantic bugs.",
    )


def _section_suspected(suspected_bugs: list[dict[str, object]]) -> str:
    return _section_suspicions(
        suspected_bugs,
        "suspected",
        "## For Review (unverified suspicions — not scored)",
        "No unverified suspicions.",
    )


def _compute_score(
    after: dict[str, float],
    ast_bugs: list[dict[str, object]],
    dynamic_bugs: list[dict[str, object]],
    api_results: list[dict[str, object]],
    suspected_bugs: list[dict[str, object]],
) -> tuple[float, float, float, float]:
    coverage_score: float = statistics.mean(after.values()) if after else 0.0
    confirmed: list[dict[str, object]] = [
        b for b in suspected_bugs if b.get("status") == "confirmed"
    ]
    all_bugs: list[dict[str, object]] = ast_bugs + dynamic_bugs + confirmed
    criticals: int = sum(1 for b in all_bugs if b["severity"] == "critical")
    warnings: int = sum(1 for b in all_bugs if b["severity"] == "warning")
    bug_score: float = max(0.0, 100.0 - criticals * 10.0 - warnings * 3.0)
    api_total: int = len(api_results)
    passed: int = sum(1 for r in api_results if r.get("passed"))
    api_score: float = (passed / api_total * 100.0) if api_total > 0 else 100.0
    quality_score: float = coverage_score * 0.4 + bug_score * 0.4 + api_score * 0.2
    return quality_score, coverage_score, bug_score, api_score


# Gate thresholds: the pass/fail decision the gig is hired to make.
DEFAULT_THRESHOLDS: dict[str, float] = {"min_coverage": 80.0, "max_new_criticals": 0}


def compute_scores(
    coverage_after: dict[str, float],
    ast_bugs: list[dict[str, object]],
    dynamic_bugs: list[dict[str, object]],
    api_results: list[dict[str, object]],
    suspected_bugs: list[dict[str, object]],
) -> dict[str, float]:
    """Public view of the four scores, keyed for persistence and trend tracking."""
    quality, coverage, bug, api = _compute_score(
        coverage_after, ast_bugs, dynamic_bugs, api_results, suspected_bugs
    )
    return {"quality": quality, "coverage": coverage, "bug": bug, "api": api}


def _trend(current: float, previous: float | None) -> str:
    if previous is None:
        return "(first run)"
    delta = current - previous
    if delta > 0.05:
        return f"▲ +{delta:.1f} vs last run"
    if delta < -0.05:
        return f"▼ {delta:.1f} vs last run"
    return "▬ no change vs last run"


def _count_new_criticals(diff: dict[str, object]) -> int:
    """Critical defects that appeared this run (new + regressed)."""
    appeared = list(diff.get("new", [])) + list(diff.get("regressed", []))
    return sum(1 for f in appeared if f.get("severity") == "critical")


def evaluate_gate(
    coverage_score: float, diff: dict[str, object], thresholds: dict[str, float]
) -> tuple[str, list[str]]:
    """The PASS/FAIL decision the gig is hired to make, as data.

    Returns ``(verdict, reasons)`` where ``verdict`` is ``"PASS"`` or ``"FAIL"``
    and ``reasons`` lists every failed threshold (empty on PASS). The report
    renders this; the CI gate turns it into a process exit code.
    """
    reasons: list[str] = []
    if not coverage_score > thresholds["min_coverage"]:
        reasons.append(
            f"coverage {coverage_score:.1f}% ≤ {thresholds['min_coverage']:.0f}%"
        )
    new_criticals = _count_new_criticals(diff)
    if new_criticals > thresholds["max_new_criticals"]:
        reasons.append(f"{new_criticals} new critical defect(s)")
    verdict = "FAIL" if reasons else "PASS"
    return verdict, reasons


def _section_scorecard(
    scores: dict[str, float],
    diff: dict[str, object],
    previous_quality: float | None,
    thresholds: dict[str, float],
) -> str:
    verdict, reasons = evaluate_gate(scores["coverage"], diff, thresholds)
    cov_cmp = ">" if scores["coverage"] > thresholds["min_coverage"] else "≤"
    lines = [
        f"**Quality Score: {scores['quality']:.1f} / 100** "
        f"{_trend(scores['quality'], previous_quality)}",
        "",
        f"**Gate: {verdict}** — coverage {scores['coverage']:.1f}% {cov_cmp} "
        f"{thresholds['min_coverage']:.0f}% · "
        f"{_count_new_criticals(diff)} new critical defect(s)",
    ]
    if reasons:
        lines.append("")
        lines.append("FAIL reasons: " + "; ".join(reasons))
    lines += [
        "",
        f"Coverage {scores['coverage']:.1f}% · Bugs {scores['bug']:.1f} · "
        f"API {scores['api']:.1f}%",
    ]
    return "\n".join(lines)


def _section_metadata(run_meta: dict[str, object]) -> str:
    sha = run_meta.get("commit_sha")
    sha_text = str(sha)[:7] if sha else "n/a"
    thresholds = run_meta.get("thresholds", DEFAULT_THRESHOLDS)
    assert isinstance(thresholds, dict)
    return (
        f"_Run {run_meta.get('run_id', '?')} · {run_meta.get('timestamp', '?')} · "
        f"commit {sha_text} · thresholds: coverage > "
        f"{thresholds['min_coverage']:.0f}%, "
        f"{thresholds['max_new_criticals']:.0f} new criticals_"
    )


def _section_changes(diff: dict[str, object]) -> str:
    coverage = diff["coverage"]
    assert isinstance(coverage, dict)
    new = list(diff["new"])
    regressed = list(diff["regressed"])
    resolved = list(diff["resolved"])
    lines = [
        "## Changes Since Last Run",
        "",
        f"New: {len(new)} · Regressed: {len(regressed)} · "
        f"Resolved: {len(resolved)} · Coverage Δ {_fmt_delta(coverage['delta'])}",
    ]
    appeared = [("new", f) for f in new] + [("regressed", f) for f in regressed]
    if appeared:
        lines += [
            "",
            "| Status | File | Line | Severity | Category |",
            "| --- | --- | --- | --- | --- |",
        ]
        for status, f in appeared:
            lines.append(
                f"| {status} | {f['file']} | {f['line']} | "
                f"{f['severity']} | {f['category']} |"
            )
    return "\n".join(lines)


DRE_PROFESSIONAL_MINIMUM = 95.0  # Capers Jones: below 95% DRE is sub-professional.


def _section_reconciliation(reconciliation: dict[str, object]) -> str:
    escape = reconciliation["escape"]
    breakdown = reconciliation["breakdown"]
    window = reconciliation["window_days"]
    assert isinstance(breakdown, dict)
    lines = ["## Critical Defect Escape Rate (DRE)", ""]
    if escape.escape_rate is None:
        lines.append(
            f"No critical defects recorded in QA or production (last {window} days)."
        )
    else:
        meets = "✓ meets" if escape.dre >= DRE_PROFESSIONAL_MINIMUM else "✗ below"
        lines.append(
            f"**Critical escape rate: {escape.escape_rate:.1f}%** · "
            f"DRE {escape.dre:.1f}% ({meets} the 95% professional minimum) — "
            f"caught {escape.caught} / escaped {escape.escaped}, last {window} days"
        )
        lines += [
            "",
            f"Escaped-bug detection: {len(breakdown['flagged'])} flagged-but-shipped"
            f" · {len(breakdown['undetected'])} undetected · "
            f"{len(breakdown['unmatched'])} unmatched",
        ]
    lines += [
        "",
        "_DRE per Capers Jones, The Economics of Software Quality (2011): "
        "caught / (caught + escaped); a production defect is an escape by definition. "
        "Trailing window; confounders (bad-fix injection, inherited defects) not "
        "modeled._",
    ]
    return "\n".join(lines)


def generate_report(
    project_path: str,
    coverage_before: dict[str, float],
    coverage_after: dict[str, float],
    ast_bugs: list[dict[str, object]],
    dynamic_bugs: list[dict[str, object]],
    api_results: list[dict[str, object]],
    suspected_bugs: list[dict[str, object]],
    *,
    diff: dict[str, object] | None = None,
    run_meta: dict[str, object] | None = None,
    previous_quality: float | None = None,
    thresholds: dict[str, float] | None = None,
    reconciliation: dict[str, object] | None = None,
) -> str:
    scores = compute_scores(
        coverage_after, ast_bugs, dynamic_bugs, api_results, suspected_bugs
    )
    header: list[str] = [f"# QAbot Report — {project_path}", ""]
    if diff is not None and run_meta is not None:
        header += [
            _section_scorecard(
                scores, diff, previous_quality, thresholds or DEFAULT_THRESHOLDS
            ),
            "",
        ]
        if reconciliation is not None:
            header += [_section_reconciliation(reconciliation), ""]
        header += [
            _section_metadata(run_meta),
            "",
            _section_changes(diff),
            "",
        ]
    else:
        header += [
            f"**Quality Score: {scores['quality']:.1f} / 100**",
            "",
            f"Coverage {scores['coverage']:.1f}% · Bugs {scores['bug']:.1f} · "
            f"API {scores['api']:.1f}%",
            "",
        ]
    body: list[str] = [
        _section_coverage(coverage_before, coverage_after),
        "",
        _section_ast_bugs(ast_bugs),
        "",
        _section_dynamic_bugs(dynamic_bugs),
        "",
        _section_semantic_bugs(suspected_bugs),
        "",
        _section_api(api_results),
        "",
        _section_suspected(suspected_bugs),
    ]
    return "\n".join(header + body)
