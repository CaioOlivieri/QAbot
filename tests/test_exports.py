import json
import xml.etree.ElementTree as ET
from pathlib import Path

from qabot.agent import exports

_THRESHOLDS = {"min_coverage": 80.0, "max_new_criticals": 0}


def _ast_bug(severity: str = "critical") -> dict[str, object]:
    return {
        "file": "ops.py",
        "line": 12,
        "severity": severity,
        "category": "off_by_one",
        "description": "inverted condition",
    }


def test_to_sarif_maps_severity_and_location() -> None:
    doc = json.loads(exports.to_sarif([_ast_bug("critical"), _ast_bug("warning")]))
    assert doc["version"] == "2.1.0"
    results = doc["runs"][0]["results"]
    assert results[0]["level"] == "error"
    assert results[1]["level"] == "warning"
    location = results[0]["locations"][0]["physicalLocation"]
    assert location["artifactLocation"]["uri"] == "ops.py"
    assert location["region"]["startLine"] == 12


def test_to_sarif_empty_is_valid_json() -> None:
    doc = json.loads(exports.to_sarif([]))
    assert doc["runs"][0]["results"] == []


def test_to_junit_coverage_fail_and_defect() -> None:
    xml = exports.to_junit({"ops.py": 50.0}, [_ast_bug()], [], [], _THRESHOLDS)
    suite = ET.fromstring(xml)
    assert suite.tag == "testsuite"
    assert suite.get("tests") == "2"
    assert suite.get("failures") == "2"
    coverage_case = next(
        c for c in suite.findall("testcase") if c.get("name") == "coverage"
    )
    assert coverage_case.find("failure") is not None


def test_to_junit_coverage_pass_no_defects() -> None:
    xml = exports.to_junit({"ops.py": 95.0}, [], [], [], _THRESHOLDS)
    suite = ET.fromstring(xml)
    assert suite.get("tests") == "1"
    assert suite.get("failures") == "0"
    assert suite.find("testcase").find("failure") is None


def test_to_junit_counts_only_confirmed_suspicions() -> None:
    suspected = [
        {**_ast_bug(), "status": "confirmed"},
        {**_ast_bug(), "status": "suspected"},
    ]
    xml = exports.to_junit({"ops.py": 95.0}, [], [], suspected, _THRESHOLDS)
    suite = ET.fromstring(xml)
    assert suite.get("tests") == "2"
    assert suite.get("failures") == "1"


def test_to_coverage_xml_line_rate_and_classes() -> None:
    root = ET.fromstring(exports.to_coverage_xml({"a.py": 80.0, "b.py": 100.0}))
    assert root.tag == "coverage"
    assert root.get("line-rate") == "0.9000"
    classes = root.findall("./packages/package/classes/class")
    assert {c.get("name") for c in classes} == {"a.py", "b.py"}


def test_write_exports_creates_three_parseable_files(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    paths = exports.write_exports(
        str(reports), {"ops.py": 90.0}, [_ast_bug()], [], [], _THRESHOLDS
    )
    assert sorted(Path(p).name for p in paths) == [
        "coverage.xml",
        "qa-results.xml",
        "qa.sarif",
    ]
    json.loads((reports / "qa.sarif").read_text())
    ET.fromstring((reports / "qa-results.xml").read_text())
    ET.fromstring((reports / "coverage.xml").read_text())
