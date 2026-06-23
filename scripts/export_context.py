import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"

IGNORED_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "reports",
}

VALID_EXTENSIONS = {
    ".py",
    ".md",
    ".json",
    ".txt",
    ".toml",
}

SECURITY_PREFIXES = (".env",)
SECURITY_FILES = {".env.keys"}
SECURITY_EXTENSIONS = {".sqlite3", ".db"}


def should_ignore(path: Path, rel: str) -> bool:
    if path.is_dir():
        return path.name in IGNORED_DIRS
    name = path.name
    if name in SECURITY_FILES:
        return True
    if any(name.startswith(p) for p in SECURITY_PREFIXES):
        return True
    if path.suffix.lower() in SECURITY_EXTENSIONS:
        return True
    return False


def walk():
    results = []
    for root_dir, dirs, files in os.walk(ROOT):
        root_path = Path(root_dir)

        # Filter directories
        dirs[:] = [
            d for d in dirs if not should_ignore(root_path / d, str(root_path / d))
        ]

        for file in files:
            fpath = root_path / file
            rel = fpath.relative_to(ROOT)

            if should_ignore(fpath, str(rel)):
                continue
            if fpath.suffix.lower() not in VALID_EXTENSIONS:
                continue

            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            results.append((rel.as_posix(), content))
    return results


def generate_report():
    tz = ZoneInfo("America/Sao_Paulo")
    now = datetime.now(tz)
    filename = now.strftime("estado_projeto_%d-%m-%y_%H.%M.md")
    out_path = REPORTS_DIR / filename
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    files = walk()

    lines = []
    lines.append("# Estado do Projeto\n")
    lines.append(
        f"**Gerado em:** {now.strftime('%d/%m/%Y às %H:%M')} (Horário de Brasília)\n"
    )
    lines.append(f"**Total de arquivos:** {len(files)}\n")
    lines.append("---\n")

    for rel_path, content in files:
        lines.append(f'<file path="{rel_path}">')
        lines.append(content)
        if not content.endswith("\n"):
            lines.append("")
        lines.append("</file>")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


if __name__ == "__main__":
    out = generate_report()
    print(f"Relatório gerado: {out}")
