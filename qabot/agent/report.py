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
    sorted_bugs = sorted(
        bugs,
        key=lambda b: (0 if b["severity"] == "critical" else 1, b["file"], b["line"]),
    )
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
    sorted_bugs = sorted(
        bugs,
        key=lambda b: (0 if b["severity"] == "critical" else 1, b["file"], b["line"]),
    )
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


def _section_semantic_bugs(suspected_bugs: list[dict[str, object]]) -> str:
    confirmed = [b for b in suspected_bugs if b.get("status") == "confirmed"]
    lines: list[str] = [
        "## Semantic Bugs (LLM, confirmed by execution)",
        "",
        "| File | Line | Severity | Description |",
        "| --- | --- | --- | --- |",
    ]
    if not confirmed:
        lines.append("No confirmed semantic bugs.")
        return "\n".join(lines)
    for b in sorted(confirmed, key=lambda b: (b["file"], b["line"])):
        lines.append(
            f"| {b['file']} | {b['line']} | {b['severity']} | {b['description']} |"
        )
    return "\n".join(lines)


def _section_suspected(suspected_bugs: list[dict[str, object]]) -> str:
    suspected = [b for b in suspected_bugs if b.get("status") == "suspected"]
    lines: list[str] = [
        "## For Review (unverified suspicions — not scored)",
        "",
        "| File | Line | Severity | Description |",
        "| --- | --- | --- | --- |",
    ]
    if not suspected:
        lines.append("No unverified suspicions.")
        return "\n".join(lines)
    for b in sorted(suspected, key=lambda b: (b["file"], b["line"])):
        lines.append(
            f"| {b['file']} | {b['line']} | {b['severity']} | {b['description']} |"
        )
    return "\n".join(lines)


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


def generate_report(
    project_path: str,
    coverage_before: dict[str, float],
    coverage_after: dict[str, float],
    ast_bugs: list[dict[str, object]],
    dynamic_bugs: list[dict[str, object]],
    api_results: list[dict[str, object]],
    suspected_bugs: list[dict[str, object]],
) -> str:
    quality_score, coverage_score, bug_score, api_score = _compute_score(
        coverage_after,
        ast_bugs,
        dynamic_bugs,
        api_results,
        suspected_bugs,
    )
    parts: list[str] = [
        f"# QAbot Report — {project_path}",
        "",
        f"**Quality Score: {quality_score:.1f} / 100**",
        "",
        f"Coverage {coverage_score:.1f}% · Bugs {bug_score:.1f} · API {api_score:.1f}%",
        "",
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
    return "\n".join(parts)
