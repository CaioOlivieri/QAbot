import sys

from qabot.agent.core import run_agent


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python -m qabot <project_path>")
        return 1

    project_path: str = sys.argv[1]
    result: str = run_agent(project_path)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
