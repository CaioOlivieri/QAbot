import argparse
import sys

from qabot.agent.core import run_agent
from qabot.agent.smoke import run_smoke


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qabot",
        description="AI agent for automated QA on Python projects.",
    )
    parser.add_argument(
        "project_path", nargs="?", help="path to the project to analyze"
    )
    parser.add_argument(
        "--tier",
        choices=("regression", "smoke"),
        default="regression",
        help=(
            "regression (default): full LLM generate + run + trend update. "
            "smoke: deterministic AST + existing suite + gate, no LLM; exits "
            "non-zero on gate FAIL — the blocking check for pull requests."
        ),
    )
    parser.add_argument(
        "--source",
        help="source dir to AST-scan in the smoke tier (default: project_path)",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args(sys.argv[1:])

    if not args.project_path:
        print("Usage: qabot <project_path> [--tier {regression,smoke}]")
        return 1

    if args.tier == "smoke":
        result = run_smoke(args.project_path, source_dir=args.source)
        print(result.report_md)
        if not result.passed:
            print(f"Gate: FAIL — {'; '.join(result.reasons)}")
            return 1
        print("Gate: PASS")
        return 0

    print(run_agent(args.project_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
