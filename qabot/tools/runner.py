import re
import subprocess


def run_command(cmd: list[str], cwd: str) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout, result.stderr


def parse_coverage(coverage_output: str) -> dict[str, float]:
    coverage: dict[str, float] = {}
    for line in coverage_output.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0].endswith(".py") and parts[-1].endswith("%"):
            name = parts[0]
            try:
                coverage[name] = float(parts[-1].rstrip("%"))
            except ValueError:
                continue
    return coverage


def parse_pytest_failures(pytest_output: str) -> list[dict[str, str | int]]:
    S, F, T = "SCANNING", "IN_FAILURES", "IN_TEST"
    state: str = S
    failures: list[dict[str, str | int]] = []
    test: str = ""
    err_type: str = ""
    desc: str = ""
    got_err: bool = False
    for line in pytest_output.splitlines():
        if "short test summary" in line:
            state = S
            continue
        if state == S:
            stripped = line.strip()
            if "FAILURES" in stripped or "ERRORS" in stripped:
                state = F
            continue
        if state == F:
            m = re.match(r"_{4,}\s+(\S+)\s+_{4,}", line)
            if m is not None:
                test = m.group(1)
                err_type = ""
                desc = ""
                got_err = False
                state = T
            continue
        if state == T:
            m3 = re.match(r"^E\s+", line)
            if m3 is not None and not got_err:
                content = line[m3.end() :]
                if ":" in content:
                    err_type, desc = content.split(":", 1)
                    err_type = err_type.strip()
                    desc = desc.strip()
                else:
                    err_type = content.strip()
                    desc = ""
                got_err = True
                continue
            m4 = re.match(r"^(.+\.py):(\d+): (\w+)$", line)
            if m4 is not None:
                file = m4.group(1)
                line_num = int(m4.group(2))
                basename = file.split("/")[-1]
                if not basename.startswith("test_"):
                    sev = "critical"
                elif err_type == "AssertionError" and any(
                    x in desc for x in (" == ", " in ", " is ")
                ):
                    sev = "critical"
                else:
                    sev = "warning"
                failures.append(
                    {
                        "file": file,
                        "line": line_num,
                        "test_name": test,
                        "severity": sev,
                        "error_type": err_type,
                        "description": desc,
                    }
                )
                state = F
    return failures
