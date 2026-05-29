import ast

from qabot.tools.fs import list_files


def analyze_file_ast(filepath: str) -> list[dict[str, str | int]]:
    findings: list[dict[str, str | int]] = []

    with open(filepath) as f:
        try:
            tree = ast.parse(f.read(), filename=filepath)
        except SyntaxError:
            return findings

    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if handler.type is None:
                findings.append(
                    {
                        "file": filepath,
                        "line": handler.lineno,
                        "severity": "critical",
                        "category": "bare_except",
                        "description": "Bare except clause without exception type",
                    }
                )
                continue

            if isinstance(handler.type, ast.Name) and handler.type.id in (
                "Exception",
                "BaseException",
            ):
                findings.append(
                    {
                        "file": filepath,
                        "line": handler.lineno,
                        "severity": "warning",
                        "category": "broad_except",
                        "description": f"Overly broad except ({handler.type.id})",
                    }
                )

            if _is_silent(handler):
                findings.append(
                    {
                        "file": filepath,
                        "line": handler.lineno,
                        "severity": "critical",
                        "category": "silent_exception",
                        "description": "Handler body only contains pass or ...",
                    }
                )

    return findings


def _is_silent(handler: ast.ExceptHandler) -> bool:
    if len(handler.body) != 1:
        return False
    stmt = handler.body[0]
    if isinstance(stmt, ast.Pass):
        return True
    if (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and stmt.value.value is Ellipsis
    ):
        return True
    return False


def analyze_project_ast(project_path: str) -> list[dict[str, str | int]]:
    all_findings: list[dict[str, str | int]] = []
    for filepath in list_files(project_path):
        all_findings.extend(analyze_file_ast(filepath))
    return all_findings
