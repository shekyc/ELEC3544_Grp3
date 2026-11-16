"""Validate frozen agent batches and import their actual outputs without relabelling."""

import json
from collections import Counter
from pathlib import Path

from musk_sentiment.config import load_config
from musk_sentiment.data.corpus import read_posts, select_window
from musk_sentiment.nlp.pipeline import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from musk_sentiment.schemas import NLPRecord, SentimentOutput
from musk_sentiment.utils.io import digest, save_records, snapshot, write_json

TOPICS = {
    "products",
    "production",
    "adoption",
    "valuation",
    "regulation",
    "technology",
    "financing",
    "macro",
    "other",
}


def import_batch_run(run_dir: Path, posts_path: Path, config_path: Path, output: Path) -> dict:
    """Fail closed on missing, stale, duplicate or inconsistent extraction artifacts."""
    manifest_path = run_dir / "frozen_run.json"
    manifest = json.loads(manifest_path.read_text())
    cfg = load_config(config_path)
    posts = read_posts(posts_path)
    if not posts or posts != select_window(posts, cfg["research"]["start"], cfg["research"]["end"]):
        raise ValueError("Use nonempty prepared study posts")
    post_map = {p.post_id: p for p in posts}
    if len(post_map) != len(posts):
        raise ValueError("Duplicate corpus IDs")
    assets = cfg["assets"]
    allowed = {a.ticker for a in assets}
    schema = SentimentOutput.model_json_schema()
    expected = {
        "corpus_sha256": digest(posts_path.read_bytes()),
        "config_sha256": digest(config_path.read_bytes()),
        "system_prompt_sha256": digest(SYSTEM_PROMPT.encode()),
        "schema_sha256": digest(json.dumps(schema, sort_keys=True).encode()),
        "prompt_version": PROMPT_VERSION,
        "posts": len(posts),
    }
    if any(manifest.get(k) != v for k, v in expected.items()):
        raise ValueError("Frozen run does not match current corpus/config/prompt/schema")
    if not isinstance(manifest.get("synthetic"), bool) or any(
        p.synthetic != manifest["synthetic"] for p in posts
    ):
        raise ValueError("Synthetic status mismatch")
    if manifest.get("human_ground_truth") is not False:
        raise ValueError("Agent outputs must not be marked human ground truth")
    for key in ("model", "reasoning_effort", "provider", "annotator_id"):
        if not manifest.get(key):
            raise ValueError(f"Missing frozen {key}")
    records = {}
    raw_artifacts = []
    batch_names = set()
    for batch in manifest["batches"]:
        name = batch["batch"]
        if name in batch_names or Path(name).name != name:
            raise ValueError("Duplicate or invalid batch name")
        batch_names.add(name)
        input_path = run_dir / "inputs" / f"{name}.json"
        result_path = run_dir / "outputs" / f"{name}.json"
        provenance_path = run_dir / "outputs" / f"{name}.provenance.json"
        payload_bytes = input_path.read_bytes()
        if digest(payload_bytes) != batch["input_sha256"]:
            raise ValueError(f"Changed frozen input: {name}")
        payload = json.loads(payload_bytes)
        if (
            payload["system_prompt"] != SYSTEM_PROMPT
            or payload["prompt_version"] != PROMPT_VERSION
            or payload["schema"] != schema
        ):
            raise ValueError(f"Prompt/schema mismatch: {name}")
        inputs = payload["posts"]
        ids = [p["post_id"] for p in inputs]
        if len(ids) != len(set(ids)) or len(ids) != batch["count"]:
            raise ValueError(f"Duplicate IDs or count mismatch: {name}")
        for supplied in inputs:
            post = post_map.get(supplied["post_id"])
            if post is None or supplied != json.loads(build_user_prompt(post, assets)):
                raise ValueError(f"Input fingerprint mismatch: {name}")
        result_bytes = result_path.read_bytes()
        provenance = json.loads(provenance_path.read_text())
        for key, value in {
            "input_sha256": digest(payload_bytes),
            "output_sha256": digest(result_bytes),
            "prompt_version": PROMPT_VERSION,
            "requested_model": manifest["model"],
            "reasoning_effort": manifest["reasoning_effort"],
            "synthetic": manifest["synthetic"],
            "human_ground_truth": False,
            "method": "model_reasoned_each_post",
        }.items():
            if provenance.get(key) != value:
                raise ValueError(f"Provenance mismatch ({key}): {name}")
        outputs = [SentimentOutput.model_validate(v) for v in json.loads(result_bytes)]
        output_ids = [v.post_id for v in outputs]
        if len(output_ids) != len(set(output_ids)) or set(output_ids) != set(ids):
            raise ValueError(f"Missing, extra or duplicate output IDs: {name}")
        for value in outputs:
            if value.post_id in records:
                raise ValueError("Duplicate IDs across batches")
            if any(a.ticker not in allowed for a in value.assets):
                raise ValueError("Unconfigured output asset")
            if not set(value.topics) <= TOPICS or len(value.topics) != len(set(value.topics)):
                raise ValueError("Invalid or duplicate topics")
            post = post_map[value.post_id]
            user = build_user_prompt(post, assets)
            parameters = {
                "reasoning_effort": manifest["reasoning_effort"],
                "annotator_id": manifest["annotator_id"],
                "execution": "model_reasoned_batch",
                "batch": name,
                "batch_input_sha256": digest(payload_bytes),
                "batch_output_sha256": digest(result_bytes),
                "provenance_sha256": digest(provenance_path.read_bytes()),
                "human_ground_truth": False,
            }
            key = digest(
                json.dumps(
                    {
                        "user": user,
                        "prompt": SYSTEM_PROMPT,
                        "version": PROMPT_VERSION,
                        "schema": schema,
                        "provider": manifest["provider"],
                        "model": manifest["model"],
                        "parameters": parameters,
                        "synthetic": post.synthetic,
                    },
                    sort_keys=True,
                ).encode()
            )
            records[value.post_id] = NLPRecord(
                input_sha256=digest(user.encode()),
                output=value,
                provider=manifest["provider"],
                model=manifest["model"],
                prompt_version=PROMPT_VERSION,
                cache_key=key,
                parameters=parameters,
                synthetic=post.synthetic,
            )
        raw_artifacts.extend([input_path, result_path, provenance_path])
    if set(records) != set(post_map):
        raise ValueError("Incomplete full-corpus batch coverage")
    ordered = [records[p.post_id] for p in posts]
    destination = output / "sentiments.json"
    if destination.exists():
        existing = [NLPRecord.model_validate(v) for v in json.loads(destination.read_text())]
        if existing != ordered:
            raise ValueError("Output exists with different records; use a new output directory")
    # Preserve raw evidence only after all batches validate; no partial final result is published.
    snapshots = [
        str(snapshot(run_dir / "snapshots", p.read_bytes(), ".json"))
        for p in [manifest_path, *raw_artifacts]
    ]
    save_records(destination, ordered)
    for record in ordered:
        write_json(output / "cache" / f"{record.cache_key}.json", record.model_dump(mode="json"))
    summary = {
        "posts": len(ordered),
        "batches": len(batch_names),
        "market_relevant": sum(r.output.market_relevant for r in ordered),
        "posts_with_assets": sum(bool(r.output.assets) for r in ordered),
        "asset_labels": sum(len(r.output.assets) for r in ordered),
        "asset_counts": dict(Counter(a.ticker for r in ordered for a in r.output.assets)),
        "sentiment_counts": dict(Counter(a.sentiment for r in ordered for a in r.output.assets)),
        "topic_counts": dict(Counter(t for r in ordered for t in r.output.topics)),
        "model": manifest["model"],
        "reasoning_effort": manifest["reasoning_effort"],
        "prompt_version": PROMPT_VERSION,
        "synthetic": manifest["synthetic"],
        "human_ground_truth": False,
        "missing_ids": [],
        "duplicate_ids": [],
        "frozen_run_sha256": digest(manifest_path.read_bytes()),
        "output_sha256": digest(destination.read_bytes()),
        "snapshots": snapshots,
        "status": "Complete schema-validated model extraction; interpretation not human-verified",
    }
    write_json(output / "summary.json", summary)
    write_json(output / "errors.json", [])
    return summary
