"""Versioned contracts shared by acquisition, NLP and future research modules."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Nonempty = Annotated[str, Field(min_length=1)]
Finite = Annotated[float, Field(allow_inf_nan=False)]
Score = Annotated[float, Field(ge=-1, le=1, allow_inf_nan=False)]
Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Naive timestamps are forbidden; supply an explicit source timezone")
    return value.astimezone(UTC)


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)
    schema_version: Literal["1"] = "1"


class RawPost(Record):
    post_id: Nonempty
    text: Nonempty
    created_at: datetime
    author: Nonempty
    is_reply: bool | None = None
    is_repost: bool | None = None
    source: Nonempty
    likes: int | None = Field(default=None, ge=0)
    engagement_observed_at: datetime | None = None
    synthetic: bool = False

    _time = field_validator("created_at")(utc)

    @field_validator("engagement_observed_at")
    @classmethod
    def optional_time(cls, value):
        return utc(value) if value is not None else None


class CleanPost(RawPost):
    is_reply: Literal[False] = False
    is_repost: Literal[False] = False
    normalized_text: Nonempty


class Asset(Record):
    ticker: Nonempty
    asset_class: Literal["stock", "etf", "crypto"]
    calendar: Nonempty
    benchmark: Nonempty
    aliases: list[Nonempty] = Field(default_factory=list)

    @model_validator(mode="after")
    def calendar_matches(self):
        if (self.asset_class == "crypto") != (self.calendar == "24/7"):
            raise ValueError("Crypto requires 24/7 calendar; securities require an exchange")
        return self


class MarketObservation(Record):
    ticker: Nonempty
    bar_start: datetime
    bar_end: datetime
    interval: Literal["1d", "1h"]
    open: float = Field(gt=0, allow_inf_nan=False)
    high: float = Field(gt=0, allow_inf_nan=False)
    low: float = Field(gt=0, allow_inf_nan=False)
    close: float = Field(gt=0, allow_inf_nan=False)
    volume: float = Field(ge=0, allow_inf_nan=False)
    adjusted: bool
    source: Nonempty
    synthetic: bool = False

    _time = field_validator("bar_start", "bar_end")(utc)

    @model_validator(mode="after")
    def valid_bar(self):
        if self.bar_end <= self.bar_start:
            raise ValueError("bar_end must follow bar_start")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("OHLC bounds inconsistent")
        return self


class AssetSentiment(Record):
    ticker: Nonempty
    sentiment: Literal["bullish", "bearish", "neutral"]
    sentiment_score: Score
    confidence: Confidence

    @model_validator(mode="after")
    def direction(self):
        score = self.sentiment_score
        if (
            (self.sentiment == "bullish" and score <= 0)
            or (self.sentiment == "bearish" and score >= 0)
            or (self.sentiment == "neutral" and score != 0)
        ):
            raise ValueError("Sentiment label and score disagree")
        return self


class SentimentOutput(Record):
    post_id: Nonempty
    market_relevant: bool
    assets: list[AssetSentiment]
    topics: list[Nonempty]
    impact_horizon: Literal["intraday", "short_term", "long_term", "unknown"]
    ambiguity: Nonempty

    @model_validator(mode="after")
    def relevant_assets(self):
        if not self.market_relevant and self.assets:
            raise ValueError("Irrelevant posts cannot have financial asset labels")
        if len({a.ticker for a in self.assets}) != len(self.assets):
            raise ValueError("Duplicate assets")
        return self


class NLPRecord(Record):
    output: SentimentOutput
    provider: Nonempty
    model: Nonempty
    prompt_version: Nonempty
    cache_key: Nonempty
    parameters: dict
    synthetic: bool


class PostAssetEvent(Record):
    event_id: Nonempty
    post_id: Nonempty
    ticker: Nonempty
    posted_at: datetime
    prediction_at: datetime
    mention_index: int = Field(ge=1)
    first_observed_mention: bool
    sentiment_score: Score
    synthetic: bool
    _time = field_validator("posted_at", "prediction_at")(utc)

    @model_validator(mode="after")
    def valid_event(self):
        if self.prediction_at < self.posted_at:
            raise ValueError("Prediction cannot precede post")
        if self.first_observed_mention != (self.mention_index == 1):
            raise ValueError("Inconsistent mention ordinal")
        return self


class EventReturn(Record):
    event_id: Nonempty
    ticker: Nonempty
    prediction_at: datetime
    baseline_at: datetime
    outcome_at: datetime
    interval: Literal["1d", "1h"]
    horizon_bars: int = Field(gt=0)
    raw_return: Finite
    benchmark_return: Finite | None = None
    abnormal_return: Finite | None = None
    synthetic: bool
    _time = field_validator("prediction_at", "baseline_at", "outcome_at")(utc)

    @model_validator(mode="after")
    def timing(self):
        if not self.baseline_at <= self.prediction_at < self.outcome_at:
            raise ValueError("Return timestamps would leak future information")
        if (self.benchmark_return is None) != (self.abnormal_return is None):
            raise ValueError("Benchmark and abnormal returns must be supplied together")
        if self.benchmark_return is not None:
            if abs(self.raw_return - self.benchmark_return - self.abnormal_return) > 1e-10:
                raise ValueError("Inconsistent benchmark-adjusted return")
        return self


class FeatureRow(Record):
    event_id: Nonempty
    ticker: Nonempty
    prediction_at: datetime
    features_available_at: datetime
    label_end: datetime
    features: dict[str, Finite]
    target: Finite
    synthetic: bool
    _time = field_validator("prediction_at", "features_available_at", "label_end")(utc)

    @model_validator(mode="after")
    def no_future_features(self):
        if not self.features_available_at <= self.prediction_at < self.label_end:
            raise ValueError("Feature availability or target timing leaks information")
        return self
