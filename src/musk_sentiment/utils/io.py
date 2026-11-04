"""Atomic writes and immutable content-addressed raw input snapshots."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".write-")
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(payload)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def save_records(path: Path, records: list[BaseModel]) -> None:
    write_json(path, [r.model_dump(mode="json") for r in records])


def snapshot(raw_dir: Path, payload: bytes, suffix: str) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{digest(payload)}{suffix}"
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise ValueError("Raw snapshot hash collision or corruption") from None
    return path
