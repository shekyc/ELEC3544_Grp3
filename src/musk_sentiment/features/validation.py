"""Conservative chronological split with overlap purge, not model training."""

from datetime import datetime

from musk_sentiment.schemas import FeatureRow, utc


def purged_split(rows: list[FeatureRow], cutoff: datetime):
    cutoff = utc(cutoff)
    ordered = sorted(rows, key=lambda row: (row.prediction_at, row.event_id))
    train = [row for row in ordered if row.label_end < cutoff]
    test = [row for row in ordered if row.prediction_at >= cutoff]
    return train, test
