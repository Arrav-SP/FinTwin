from __future__ import annotations

"""Assemble the folder that is pushed to the hosting service (a Hugging Face Space).

The Space is its own Git repository with its own Dockerfile and README, and it refuses files
over 10 MB without Git LFS. This script copies what the all-in-one image needs into
build/space, puts the Space's Dockerfile, README and start script at its top, and splits the
database dump into pieces small enough to push. build/ is not in version control.
"""

import argparse
import shutil
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
PART_BYTES = 8 * 1024 * 1024
COPIED = ("backend", "database", "scripts", "web", "bundled")
SKIPPED = shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", "dist", ".env", ".env.*", "database.sql.gz")
CRLF, LF = bytes([13, 10]), bytes([10])


def build_space(project: Path = PROJECT, out: Path | None = None, part_bytes: int = PART_BYTES) -> Path:
    out = out or project / "build" / "space"
    out.mkdir(parents=True, exist_ok=True)
    # Start clean, but keep .git: once the folder is linked to the Space, a rebuild is just a new commit.
    for existing in out.iterdir():
        if existing.name == ".git":
            continue
        shutil.rmtree(existing) if existing.is_dir() else existing.unlink()

    for name in COPIED:
        if (project / name).is_dir():
            shutil.copytree(project / name, out / name, ignore=SKIPPED)
    for file in (project / "deploy" / "space").iterdir():
        shutil.copy2(file, out / file.name)
    # A checkout on Windows may have CRLF line endings, which break a shell script in a Linux container.
    for script in out.rglob("*.sh"):
        script.write_bytes(script.read_bytes().replace(CRLF, LF))

    dump = project / "bundled" / "database.sql.gz"
    if dump.is_file():
        with dump.open("rb") as source:
            index = 0
            while chunk := source.read(part_bytes):
                (out / "bundled" / f"database.sql.gz.part{index:02d}").write_bytes(chunk)
                index += 1
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assemble build/space, the folder pushed to the Hugging Face Space.")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    target = build_space(out=args.output)
    files = [path for path in target.rglob("*") if path.is_file() and ".git" not in path.parts]
    print(f"{target}: {len(files)} files, {sum(path.stat().st_size for path in files) / 1e6:.1f} MB, largest {max(path.stat().st_size for path in files) / 1e6:.1f} MB")
