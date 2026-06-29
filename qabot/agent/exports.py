"""Machine-readable QA exports emitted next to ``qa_report.md``.

- **SARIF** (`qa.sarif`): static (AST) findings → GitHub code-scanning annotations.
- **JUnit XML** (`qa-results.xml`): the gate + defects as test cases, for CI dashboards.
- **Cobertura** (`coverage.xml`): real line-level data when available, otherwise a
  per-module coverage summary.

Serializers are pure (return strings); ``write_exports`` does the I/O. When a real
line-level ``coverage.xml`` (produced by ``coverage.py --cov-report=xml``) is
supplied, it is written verbatim; otherwise ``to_coverage_xml`` synthesizes a
summary from the parsed per-module percentages.
"""

import json
import os
import statistics
import xml.etree.ElementTree as ET

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
_TOOL_URI = "https://github.com/CaioOlivieri/QAbot"


def _sarif_level(severity: str) -> str:
    return "error" if severity == "critical" else "warning"


def to_sarif(ast_bugs: list[dict[str, object]]) -> str:
    """Static findings as a SARIF 2.1.0 document."""
    results = [
        {
            "ruleId": str(bug.get("category", "bug")),
            "level": _sarif_level(str(bug.get("severity", "warning"))),
            "message": {"text": str(bug.get("description", ""))},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": str(bug.get("file", ""))},
                        "region": {"startLine": int(bug.get("line") or 1)},
                    }
                }
            ],
        }
        for bug in ast_bugs
    ]
    doc = {
        "version": SARIF_VERSION,
        "$schema": SARIF_SCHEMA,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "QAbot",
                        "informationUri": _TOOL_URI,
                        "rules": [],
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(doc, indent=2)


def coverage_xml_has_lines(xml_text: str) -> bool:
    """Return *True* if *xml_text* is a Cobertura XML containing ≥1 ``<line>``."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return False
    return next(root.iter("line"), None) is not None


def _xml_document(element: ET.Element) -> str:
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        element, encoding="unicode"
    )


def to_junit(
    coverage: dict[str, float],
    ast_bugs: list[dict[str, object]],
    dynamic_bugs: list[dict[str, object]],
    suspected_bugs: list[dict[str, object]],
    thresholds: dict[str, float],
) -> str:
    """QA checks as a JUnit test suite: one coverage gate + one case per defect."""
    confirmed = [b for b in suspected_bugs if b.get("status") == "confirmed"]
    defects = list(ast_bugs) + list(dynamic_bugs) + confirmed
    coverage_score = statistics.mean(coverage.values()) if coverage else 0.0
    coverage_ok = coverage_score > thresholds["min_coverage"]

    suite = ET.Element("testsuite", name="qabot")
    cov_case = ET.SubElement(suite, "testcase", classname="qabot.gate", name="coverage")
    if not coverage_ok:
        failure = ET.SubElement(
            cov_case,
            "failure",
            message=(
                f"coverage {coverage_score:.1f}% <= {thresholds['min_coverage']:.0f}%"
            ),
        )
        failure.text = f"Mean coverage {coverage_score:.1f}% does not exceed threshold."

    for bug in defects:
        case = ET.SubElement(
            suite,
            "testcase",
            classname="qabot.defect",
            name=f"{bug.get('file', '')}:{bug.get('line', '')}",
        )
        failure = ET.SubElement(
            case, "failure", message=str(bug.get("description", ""))
        )
        failure.text = str(bug.get("severity", "warning"))

    suite.set("tests", str(1 + len(defects)))
    suite.set("failures", str((0 if coverage_ok else 1) + len(defects)))
    return _xml_document(suite)


def to_coverage_xml(coverage: dict[str, float]) -> str:
    """Per-module coverage as a minimal Cobertura summary."""
    overall = (statistics.mean(coverage.values()) / 100.0) if coverage else 0.0
    root = ET.Element(
        "coverage",
        {"line-rate": f"{overall:.4f}", "branch-rate": "0", "version": "qabot"},
    )
    packages = ET.SubElement(root, "packages")
    package = ET.SubElement(
        packages, "package", {"name": ".", "line-rate": f"{overall:.4f}"}
    )
    classes = ET.SubElement(package, "classes")
    for module, pct in sorted(coverage.items()):
        cls = ET.SubElement(
            classes,
            "class",
            {"name": module, "filename": module, "line-rate": f"{pct / 100.0:.4f}"},
        )
        ET.SubElement(cls, "methods")
        ET.SubElement(cls, "lines")
    return _xml_document(root)


def write_exports(
    reports_dir: str,
    coverage: dict[str, float],
    ast_bugs: list[dict[str, object]],
    dynamic_bugs: list[dict[str, object]],
    suspected_bugs: list[dict[str, object]],
    thresholds: dict[str, float],
    coverage_xml: str | None = None,
) -> list[str]:
    """Write the three exports into ``reports_dir``; return the paths written.

    When *coverage_xml* is provided and contains real line-level data
    (``<line>`` elements), it is written verbatim as ``coverage.xml``; otherwise
    the per-module summary from :func:`to_coverage_xml` is used as a fallback.
    """
    os.makedirs(reports_dir, exist_ok=True)
    if coverage_xml is not None and coverage_xml_has_lines(coverage_xml):
        cov_content = coverage_xml
    else:
        cov_content = to_coverage_xml(coverage)
    files = {
        "qa.sarif": to_sarif(ast_bugs),
        "qa-results.xml": to_junit(
            coverage, ast_bugs, dynamic_bugs, suspected_bugs, thresholds
        ),
        "coverage.xml": cov_content,
    }
    written: list[str] = []
    for name, content in files.items():
        path = os.path.join(reports_dir, name)
        with open(path, "w") as f:
            f.write(content)
        written.append(path)
    return written
