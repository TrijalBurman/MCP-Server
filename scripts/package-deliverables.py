"""Package the publishable checkout, excluding local runtime and personal data.

Run after staging the intended source/document files. Frozen research archives are copied
unchanged. SHA256SUMS inside the ZIP covers every other archive member.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "output/localmind-final-presentation-package.zip"
CHECKSUM = ARCHIVE.with_suffix(".sha256")
EXCLUDED_PARTS = {".git", ".venv", ".runtime", ".local-copilot", "__pycache__",
                  ".pytest_cache", ".ruff_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".sqlite", ".sqlite3", ".db", ".gguf", ".safetensors"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def project_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "-z"],
        cwd=ROOT, check=True, capture_output=True,
    )
    files = []
    for name in sorted(set(result.stdout.decode().split("\0")) - {""}):
        path = ROOT / name
        if path in {ARCHIVE, CHECKSUM, ARCHIVE.with_suffix(".zip.tmp")} \
                or EXCLUDED_PARTS.intersection(Path(name).parts):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES or path.name.startswith(".env"):
            continue
        if not path.is_file() or path.is_symlink():
            continue
        if path.stat().st_size >= 95 * 1024 * 1024:
            raise ValueError(f"Unexpected oversized publication file: {name}")
        files.append(path)
    return files


def write_member(archive: ZipFile, name: str, data: bytes):
    entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    entry.compress_type = ZIP_DEFLATED
    entry.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
    archive.writestr(entry, data)


def main():
    files = project_files()
    required = {"README.md", "copilot/agent.py", "output/README.md",
                "output/pdf/localmind-ieee-research-paper.pdf",
                "output/blackbook/localmind-blackbook-60-pages.pdf",
                "research/model-selection/README.md"}
    names = {path.relative_to(ROOT).as_posix() for path in files}
    if not required.issubset(names):
        raise ValueError(f"Missing publication files: {sorted(required - names)}")
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    temporary = ARCHIVE.with_suffix(".zip.tmp")
    manifest = []
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            for path in files:
                name, data = path.relative_to(ROOT).as_posix(), path.read_bytes()
                write_member(archive, name, data)
                manifest.append(f"{sha256(data)}  {name}\n")
            write_member(archive, "SHA256SUMS", "".join(manifest).encode())
        with ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ValueError("ZIP integrity check failed")
            checks = {line[66:]: line[:64] for line in archive.read("SHA256SUMS").decode().splitlines()}
            assert set(checks) == set(archive.namelist()) - {"SHA256SUMS"}
            assert all(sha256(archive.read(name)) == digest for name, digest in checks.items())
        temporary.replace(ARCHIVE)
    finally:
        temporary.unlink(missing_ok=True)
    CHECKSUM.write_text(f"{sha256(ARCHIVE.read_bytes())}  {ARCHIVE.name}\n")
    print(f"Verified {len(files)} project files in {ARCHIVE.relative_to(ROOT)}")
    print(f"Archive size: {ARCHIVE.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
