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
