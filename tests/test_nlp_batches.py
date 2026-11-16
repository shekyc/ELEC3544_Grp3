import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from musk_sentiment.config import load_config
from musk_sentiment.nlp.batches import import_batch_run
from musk_sentiment.nlp.pipeline import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from musk_sentiment.schemas import CleanPost, SentimentOutput
from musk_sentiment.utils.io import digest, save_records, write_json


@pytest.fixture
def batch_run(tmp_path):
    config = tmp_path / "config.toml"
    config.write_bytes(Path("configs/project.toml").read_bytes())
    assets = load_config(config)["assets"]
    posts = [
        CleanPost(
            post_id="18446744073709551615",
            text="Tesla",
            normalized_text="Tesla",
            created_at=datetime(2020, 1, 1, tzinfo=UTC),
            author="elonmusk",
            source="fixture",
            synthetic=True,
        )
    ]
    corpus = tmp_path / "posts.json"
    save_records(corpus, posts)
    run = tmp_path / "run"
    schema = SentimentOutput.model_json_schema()
    input_path = run / "inputs/batch_01.json"
    write_json(
        input_path,
        {
            "system_prompt": SYSTEM_PROMPT,
            "prompt_version": PROMPT_VERSION,
            "schema": schema,
            "posts": [json.loads(build_user_prompt(p, assets)) for p in posts],
        },
    )
    outputs = [
        {
            "post_id": posts[0].post_id,
            "market_relevant": True,
            "assets": [
                {"ticker": "TSLA", "sentiment": "neutral", "sentiment_score": 0, "confidence": 0.5}
            ],
            "topics": ["other"],
            "impact_horizon": "unknown",
            "ambiguity": "fixture",
        }
    ]
    write_json(run / "outputs/batch_01.json", outputs)
    write_json(
        run / "outputs/batch_01.provenance.json",
        {
            "input_sha256": digest(input_path.read_bytes()),
            "output_sha256": digest((run / "outputs/batch_01.json").read_bytes()),
            "prompt_version": PROMPT_VERSION,
            "requested_model": "fixture",
            "reasoning_effort": "low",
            "synthetic": True,
            "human_ground_truth": False,
            "method": "model_reasoned_each_post",
        },
    )
    write_json(
        run / "frozen_run.json",
        {
            "corpus_sha256": digest(corpus.read_bytes()),
            "config_sha256": digest(config.read_bytes()),
            "system_prompt_sha256": digest(SYSTEM_PROMPT.encode()),
            "schema_sha256": digest(json.dumps(schema, sort_keys=True).encode()),
            "prompt_version": PROMPT_VERSION,
            "posts": 1,
            "synthetic": True,
            "human_ground_truth": False,
            "model": "fixture",
            "reasoning_effort": "low",
            "provider": "synthetic-fixture",
            "annotator_id": "fixture",
            "batches": [
                {"batch": "batch_01", "count": 1, "input_sha256": digest(input_path.read_bytes())}
            ],
        },
    )
    return run, corpus, config, tmp_path / "final"


def change_output(run, mutate):
    path = run / "outputs/batch_01.json"
    values = json.loads(path.read_text())
    mutate(values)
    write_json(path, values)
    sidecar = run / "outputs/batch_01.provenance.json"
    metadata = json.loads(sidecar.read_text())
    metadata["output_sha256"] = digest(path.read_bytes())
    write_json(sidecar, metadata)


def test_import_preserves_ids_and_fingerprints_and_is_idempotent(batch_run):
    run, corpus, config, output = batch_run
    summary = import_batch_run(*batch_run)
    records = json.loads((output / "sentiments.json").read_text())
    assert summary["posts"] == summary["asset_labels"] == 1
    assert records[0]["output"]["post_id"] == "18446744073709551615"
    p = CleanPost.model_validate(json.loads(corpus.read_text())[0])
    assert records[0]["input_sha256"] == digest(
        build_user_prompt(p, load_config(config)["assets"]).encode()
    )
    assert records[0]["synthetic"] is True
    assert import_batch_run(*batch_run) == summary


@pytest.mark.parametrize(
    "change,match",
    [
        (lambda rows: rows.clear(), "output IDs"),
        (lambda rows: rows.append(rows[0]), "output IDs"),
        (lambda rows: rows[0].update(post_id="123"), "output IDs"),
        (lambda rows: rows[0]["assets"][0].update(ticker="FAKE"), "Unconfigured"),
        (lambda rows: rows[0].update(topics=["invented"]), "topics"),
    ],
)
def test_invalid_outputs_never_publish_partial_final(batch_run, change, match):
    run, _, _, output = batch_run
    change_output(run, change)
    with pytest.raises(ValueError, match=match):
        import_batch_run(*batch_run)
    assert not (output / "sentiments.json").exists()


def test_stale_source_and_provenance_rejected(batch_run):
    run, corpus, _, _ = batch_run
    original = corpus.read_bytes()
    corpus.write_bytes(original + b"\n")
    with pytest.raises(ValueError, match="Frozen run"):
        import_batch_run(*batch_run)
    corpus.write_bytes(original)
    sidecar = run / "outputs/batch_01.provenance.json"
    metadata = json.loads(sidecar.read_text())
    metadata["requested_model"] = "wrong-model"
    write_json(sidecar, metadata)
    with pytest.raises(ValueError, match="requested_model"):
        import_batch_run(*batch_run)


def test_different_existing_final_is_preserved(batch_run):
    import_batch_run(*batch_run)
    run, _, _, output = batch_run
    original = (output / "sentiments.json").read_bytes()
    change_output(run, lambda rows: rows[0].update(ambiguity="changed"))
    with pytest.raises(ValueError, match="different records"):
        import_batch_run(*batch_run)
    assert (output / "sentiments.json").read_bytes() == original
