import glob
import os


def list_files(path: str, pattern: str = "**/*.py") -> list[str]:
    return glob.glob(os.path.join(path, pattern), recursive=True)


def read_file(path: str) -> str:
    with open(path) as f:
        return f.read()


def write_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
