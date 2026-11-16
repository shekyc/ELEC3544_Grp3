"""Exact-ID corpus selection and source comparison; never fuzzy-repair identifiers."""

import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from musk_sentiment.schemas import CleanPost
from musk_sentiment.utils.io import digest, save_records, write_json


def read_posts(path: Path):
    values = json.loads(path.read_text())  # pandas inference can round 19-digit IDs
    for value in values:
        if not isinstance(value.get("post_id"), str):
            raise ValueError("Post IDs must already be strings; return to the original source")
        if value.get("is_reply") is not False or value.get("is_repost") is not False:
            raise ValueError("Explicit verified original-post flags are required")
    posts = [CleanPost.model_validate(v) for v in values]
    if len({p.post_id for p in posts}) != len(posts):
        raise ValueError("Duplicate post IDs; re-import the raw corpus")
    return sorted(posts, key=lambda p: (p.created_at, p.post_id))


def select_window(posts, start, end):
    lo, hi = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    if hi <= lo:
        raise ValueError("end must follow start")
    return [p for p in posts if lo <= p.created_at < hi]


def prepare_corpus(path, output, start, end):
    posts = select_window(read_posts(path), start, end)
    counts = Counter(p.created_at.strftime("%Y-%m") for p in posts)
    months = [
        str(m) for m in pd.period_range(start, pd.Timestamp(end) - pd.Timedelta(days=1), freq="M")
    ]
    report = {
        "input_sha256": digest(path.read_bytes()),
        "start": start,
        "end_exclusive": end,
        "rows": len(posts),
        "monthly_counts": {m: counts[m] for m in months},
        "empty_months": [m for m in months if not counts[m]],
        "sources": dict(Counter(p.source for p in posts)),
        "completeness": "Not established; reconcile against the original source",
        "synthetic": any(p.synthetic for p in posts),
    }
    save_records(output / "posts.json", posts)
    write_json(output / "quality.json", report)
    return report


def compare_corpora(left: Path, right: Path):
    """Accept CSV/JSON for diagnostics without coercing or correcting source IDs."""

    def read(path):
        if path.suffix.lower() == ".csv":
            with path.open(newline="", encoding="utf-8-sig") as f:
                return list(csv.DictReader(f))
        return json.loads(path.read_text())

    a, b = read(left), read(right)
    by_text = defaultdict(list)
    for row in a:
        by_text[row.get("text", row.get("fullText", ""))].append(row)
    mismatches = []
    for row in b:
        matches = by_text.get(row.get("text", row.get("fullText", "")), [])
        if len(matches) == 1:
            old = matches[0]
            x, y = old.get("post_id", old.get("id")), row.get("post_id", row.get("id"))
            if x != y:
                mismatches.append(
                    {
                        "left_id": x,
                        "right_id": y,
                        "same_text": True,
                        "left_time": old.get("created_at"),
                        "right_time": row.get("created_at"),
                        "action": "review raw source; not repaired",
                    }
                )
    normalized = defaultdict(list)
    for row in a:
        normalized[
            " ".join(html.unescape(row.get("text", row.get("fullText", ""))).split())
        ].append(row)
    normalized_counts = Counter()
    for row in b:
        key = " ".join(html.unescape(row.get("text", row.get("fullText", ""))).split())
        normalized_counts[len(normalized.get(key, []))] += 1
    ids_a = {str(r.get("post_id", r.get("id"))) for r in a}
    ids_b = {str(r.get("post_id", r.get("id"))) for r in b}
    return {
        "left_sha256": digest(left.read_bytes()),
        "right_sha256": digest(right.read_bytes()),
        "left_rows": len(a),
        "right_rows": len(b),
        "id_intersection": len(ids_a & ids_b),
        "only_left": sorted(ids_a - ids_b),
        "only_right": sorted(ids_b - ids_a),
        "exact_text_id_mismatches": mismatches,
        "normalized_text_candidate_counts": dict(normalized_counts),
        "normalization": "HTML entity decoding and whitespace only; diagnostic, not ID repair",
    }


def import_kaggle(path, output, raw_dir):
    """Preserve missing flags; establish author and check ID using the source status URL."""
    import io
    from urllib.parse import urlparse

    from musk_sentiment.data.posts import import_posts
    from musk_sentiment.utils.io import snapshot

    raw = snapshot(raw_dir, path.read_bytes(), ".csv")
    buffer = io.StringIO()
    fields = ["post_id", "text", "created_at", "author", "is_reply", "is_repost", "likes"]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    rejected = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for line, row in enumerate(csv.DictReader(f), 2):
            url = urlparse(row.get("twitterUrl") or row.get("url") or "")
            parts = url.path.strip("/").split("/")
            if (
                url.hostname not in {"twitter.com", "www.twitter.com", "x.com", "www.x.com"}
                or len(parts) != 3
                or parts[1] != "status"
                or parts[2] != row.get("id")
            ):
                rejected.append(
                    {
                        "line": line,
                        "post_id": row.get("id"),
                        "reason": "Missing/invalid status URL or ID disagreement",
                    }
                )
                continue
            writer.writerow(
                dict(
                    post_id=row["id"],
                    text=row["fullText"],
                    created_at=row["createdAt"],
                    author=parts[0],
                    is_reply=row.get("isReply", ""),
                    is_repost=row.get("isRetweet", ""),
                    likes=row.get("likeCount", ""),
                )
            )
    canonical = snapshot(raw_dir, buffer.getvalue().encode(), ".canonical.csv")
    posts, report = import_posts(canonical, output, raw_dir, "kaggle-dadalyndell-2025")
    report.update(
        original_raw_snapshot=str(raw),
        original_sha256=digest(path.read_bytes()),
        source_identity_rejections=rejected,
        conversion="URL-verified ID/author; blank original-status flags remain unknown",
    )
    write_json(output / "posts_quality.json", report)
    return report
