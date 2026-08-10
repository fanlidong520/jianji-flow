from __future__ import annotations

import re
from pathlib import Path


_SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")


def reject_url_or_protocol(path_text: str) -> None:
    """Reject URI-like input while allowing Windows drive-letter paths."""
    normalized = path_text.strip()
    if normalized.startswith(("//", "\\\\")):
        raise ValueError(f"URL or protocol paths are not allowed: {path_text}")
    if _SCHEME_PATTERN.match(normalized) and not _WINDOWS_DRIVE_PATTERN.match(normalized):
        raise ValueError(f"URL or protocol paths are not allowed: {path_text}")


def resolve_existing_file(path_text: str) -> Path:
    reject_url_or_protocol(path_text)
    path = Path(path_text).resolve(strict=True)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def resolve_existing_dir(path_text: str) -> Path:
    reject_url_or_protocol(path_text)
    path = Path(path_text).resolve(strict=True)
    if not path.is_dir():
        raise FileNotFoundError(path)
    return path


def ensure_inside(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"Path escapes root: {candidate}") from exc
    return resolved_candidate


def make_output_dir(root: Path, name: str) -> Path:
    reject_url_or_protocol(name)
    child = Path(name)
    if child.is_absolute():
        raise ValueError(f"Output directory name must be relative: {name}")

    output_dir = ensure_inside(root, root / child)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
