"""Interchangeable provider protocol and a free, loopback-only Ollama adapter."""

from typing import Protocol

import httpx

from musk_sentiment.schemas import SentimentOutput


class Provider(Protocol):
    name: str
    model: str
    parameters: dict
    synthetic: bool

    def generate(self, system: str, user: str) -> str: ...


class OllamaProvider:
    name = "ollama-local"
    synthetic = False

    def __init__(self, model: str):
        self.requested_model = model
        self.parameters = {"temperature": 0, "seed": 3544}
        self.url = "http://127.0.0.1:11434"
        # Require installed local weights. Never pull or invoke a cloud model implicitly.
        with httpx.Client(timeout=10, trust_env=False) as client:
            response = client.get(f"{self.url}/api/tags")
            response.raise_for_status()
            models = response.json()["models"]
            entry = next((m for m in models if m["name"] in {model, model + ":latest"}), None)
            if not entry or not entry.get("digest"):
                raise ValueError("Install a local Ollama model before running NLP")
            info = client.post(f"{self.url}/api/show", json={"model": entry["name"]})
            info.raise_for_status()
            if info.json().get("remote_host") or info.json().get("remote_model"):
                raise ValueError("Cloud-backed models require a separately approved adapter")
            self.requested_model = entry["name"]
            self.model = f"{entry['name']}@{entry['digest']}"

    def generate(self, system: str, user: str) -> str:
        with httpx.Client(timeout=180, trust_env=False) as client:
            response = client.post(
                f"{self.url}/api/chat",
                json={
                    "model": self.requested_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "format": SentimentOutput.model_json_schema(),
                    "stream": False,
                    "options": self.parameters,
                },
            )
            response.raise_for_status()
            return response.json()["message"]["content"]


class SyntheticProvider:
    """Deterministic wiring fixture, never an empirical financial classifier."""

    name = "synthetic-fixture"
    model = "fixture-v1"
    parameters = {}
    synthetic = True

    def generate(self, system: str, user: str) -> str:
        import json

        payload = json.loads(user)
        return json.dumps(
            {
                "post_id": payload["post_id"],
                "market_relevant": True,
                "assets": [
                    {
                        "ticker": payload["asset_universe"][0]["ticker"],
                        "sentiment": "neutral",
                        "sentiment_score": 0,
                        "confidence": 0,
                    }
                ],
                "topics": ["synthetic_fixture"],
                "impact_horizon": "unknown",
                "ambiguity": "Synthetic fixture; not model inference",
            }
        )
