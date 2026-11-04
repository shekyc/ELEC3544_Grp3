"""Conservative CSV ingestion: unknown reply/repost flags are never guessed."""

import csv
import io
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
from pytz.exceptions import AmbiguousTimeError, NonExistentTimeError

from musk_sentiment.schemas import CleanPost, RawPost
from musk_sentiment.utils.io import digest, save_records, snapshot, write_json


def timestamp(value: str, source_timezone: str | None = None) -> datetime:
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        raise ValueError("Missing timestamp")
    if ts.tzinfo is None:
        if source_timezone is None:
            raise ValueError("Naive timestamp needs --source-timezone")
        try:
            ts = ts.tz_localize(source_timezone, ambiguous="raise", nonexistent="raise")
        except (AmbiguousTimeError, NonExistentTimeError) as exc:
            raise ValueError(f"Ambiguous or nonexistent local timestamp: {value}") from exc
    return ts.tz_convert("UTC").to_pydatetime()


def flag(value: str | None) -> bool | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise ValueError(f"Invalid boolean: {value!r}")


def import_posts(
    path: Path,
    output_dir: Path,
    raw_dir: Path,
    source: str,
    column_map: dict[str, str] | None = None,
    source_timezone: str | None = None,
    author: str = "elonmusk",
    synthetic: bool = False,
) -> tuple[list[CleanPost], dict]:
    payload = path.read_bytes()
    raw_path = snapshot(raw_dir, payload, ".csv")
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    mapping = column_map or {}
    required = ["post_id", "text", "created_at", "author"]
    missing = [key for key in required if mapping.get(key, key) not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"Missing CSV columns: {missing}; provide a column mapping JSON file")
    counts = Counter()
    rejected = []
    valid = {}
    conflicted = set()
    for line, row in enumerate(reader, 2):
        counts["input_rows"] += 1
        values = {
            key: row.get(mapping.get(key, key))
            for key in [*required, "is_reply", "is_repost", "likes", "engagement_observed_at"]
        }
        try:
            post = RawPost(
                post_id=values["post_id"],
                text=values["text"],
                created_at=timestamp(values["created_at"], source_timezone),
                author=values["author"],
                source=source,
                is_reply=flag(values["is_reply"]),
                is_repost=flag(values["is_repost"]),
                likes=int(values["likes"]) if values["likes"] else None,
                engagement_observed_at=timestamp(values["engagement_observed_at"], source_timezone)
                if values["engagement_observed_at"]
                else None,
                synthetic=synthetic,
            )
        except (ValueError, TypeError) as exc:
            counts["invalid_rows"] += 1
            rejected.append({"line": line, "reason": str(exc)})
            continue
        if post.post_id in valid:
            counts["duplicate_rows"] += 1
            previous = valid[post.post_id]
            fields = ("text", "created_at", "author", "is_reply", "is_repost")
            if any(getattr(previous, key) != getattr(post, key) for key in fields):
                conflicted.add(post.post_id)
            continue
        valid[post.post_id] = post
    cleaned = []
    for post in valid.values():
        if post.post_id in conflicted:
            counts["conflicting_ids_excluded"] += 1
        elif post.author.lstrip("@").lower() != author.lstrip("@").lower():
            counts["other_author"] += 1
        elif post.is_reply or post.is_repost:
            counts["reply_or_repost"] += 1
        elif post.is_reply is None or post.is_repost is None:
            counts["unknown_original_status"] += 1
        else:
            cleaned.append(
                CleanPost(**post.model_dump(), normalized_text=" ".join(post.text.split()))
            )
    cleaned.sort(key=lambda p: (p.created_at, p.post_id))
    counts["clean_rows"] = len(cleaned)
    report = {
        "source": source,
        "sha256": digest(payload),
        "raw_snapshot": str(raw_path),
        "synthetic": synthetic,
        "counts": dict(counts),
        "invalid_rows": rejected,
        "coverage_start": cleaned[0].created_at.isoformat() if cleaned else None,
        "coverage_end": cleaned[-1].created_at.isoformat() if cleaned else None,
        "posts_per_month": dict(Counter(p.created_at.strftime("%Y-%m") for p in cleaned)),
        "completeness": "Unknown: counts and observed range do not establish archive completeness",
    }
    save_records(output_dir / "posts.json", cleaned)
    write_json(output_dir / "posts_quality.json", report)
    return cleaned, report
