"""Offline checks for event-time windows, non-post controls, matching and influence."""

from datetime import timedelta
from types import SimpleNamespace

import numpy as np
from test_minute_analysis import dt

from musk_sentiment.analysis.minute import SessionClock
from musk_sentiment.analysis.validation import (
    event_profiles,
    influence_checks,
    matching_distances,
    observed_posts_between,
    preconditions,
)
from musk_sentiment.schemas import MinuteBar

SETTINGS = {
    "pre_minutes": 30,
    "post_minutes": 60,
    "matching_pre_end_minutes": 5,
    "exclude_other_posts_pre_minutes": 30,
    "exclude_other_posts_post_minutes": 60,
    "seed": 3544,
    "bootstrap_repetitions": 20,
}


class Store:
    def __init__(self):
        self.requests = []

    def window(self, ticker, start, count):
        self.requests.append((ticker, start, count))
        return [
            MinuteBar(t=start + timedelta(minutes=i), o=100, h=100, l=100, c=100, v=10, n=2)
            for i in range(count)
        ]


def test_nonpost_controls_exclude_boundaries_and_count_other_simultaneous_posts():
    at = dt("2021-01-01T00:00:00Z")
    times = [at, at, at + timedelta(minutes=60)]
    assert observed_posts_between(times, at, at + timedelta(minutes=60)) == 3
    assert observed_posts_between(times, at, at + timedelta(minutes=60), at) == 2


def test_matching_uses_only_features_and_handles_constant_dimensions():
    x = np.array([1.0, 2.0, 3.0])
    candidates = np.array([[1.0, 2.0, 3.0], [2.0, 2.0, 5.0], [3.0, 2.0, 8.0]])
    distances = matching_distances(x, candidates)
    assert distances[0] == 0 and np.isfinite(distances).all()
    assert distances[1] < distances[2]


def test_preconditions_end_five_minutes_before_publication_and_respect_dst():
    clock = SessionClock("2020-01-01", "2022-01-01")
    store = Store()
    posted = dt("2021-03-15T15:00:41Z")
    preconditions(
        store, clock, "TSLA", "SPY", dt("2021-03-15T15:01:00Z"), posted, "regular", SETTINGS
    )
    assert len(store.requests) == 2
    for _, start, count in store.requests:
        assert count == 25 and start + timedelta(minutes=count) == dt("2021-03-15T14:55:00Z")
        assert start + timedelta(minutes=count) < posted


def test_profiles_no_session_splicing_and_delayed_open_has_no_pretend_prepath():
    clock = SessionClock("2020-01-01", "2022-01-01")
    assignments = [
        {
            "ticker": "TSLA",
            "cohort": "regular",
            "post_id": "1",
            "posted_at": "2021-03-15T15:00:41Z",
            "entry_at": "2021-03-15T15:01:00Z",
        },
        {
            "ticker": "TSLA",
            "cohort": "regular",
            "post_id": "2",
            "posted_at": "2021-03-15T13:35:00Z",
            "entry_at": "2021-03-15T13:35:00Z",
        },
        {
            "ticker": "TSLA",
            "cohort": "next_opening",
            "post_id": "3",
            "posted_at": "2021-03-14T12:00:00Z",
            "entry_at": "2021-03-15T13:30:00Z",
        },
    ]
    result = event_profiles(assignments, Store(), clock, SETTINGS)
    assert len(result["paths"]) == 2 and len(result["rejections"]) == 1
    immediate, opening = result["paths"]
    assert immediate["offset_minutes"][0] == -30
    assert immediate["offset_minutes"][-1] == 60
    assert immediate["publication_offset_seconds"] == 41
    assert set(immediate["cumulative_return"]) == {0.0}
    assert opening["offset_minutes"][0] == 0 and opening["pre_return"] is None


def test_leave_one_day_out_removes_all_posts_on_that_day_and_isolation_is_strict():
    entries = [dt("2021-01-01T12:00:00Z"), dt("2021-01-01T12:20:00Z"), dt("2021-01-02T12:00:00Z")]
    rows = [
        SimpleNamespace(
            ticker="BTC-USD",
            cohort="crypto_24h",
            horizon_minutes=5,
            posted_at=at,
            entry_at=at,
            forward_return=value,
            benchmark_adjusted_return=None,
            relative_volume=None,
            relative_trade_count=None,
            relative_volatility=None,
        )
        for at, value in zip(entries, [0.1, 0.3, -0.1], strict=True)
    ]
    posts = [SimpleNamespace(created_at=at) for at in entries]
    result = influence_checks(rows, posts, SETTINGS)["summaries"][0]
    assert result["days"] == 2
    assert result["leave_one_day_out"]["2021-01-01"] == -0.1
    assert result["leave_one_day_out"]["2021-01-02"] == 0.2
    assert result["isolated_events"] == 1


def test_matched_controls_are_past_nonpost_times_and_do_not_select_on_response():
    from musk_sentiment.analysis.validation import matched_placebos

    clock = SessionClock("2020-01-01", "2022-01-01")
    at = dt("2021-02-01T12:00:30Z")
    event = SimpleNamespace(
        event_id="e",
        post_id="p",
        ticker="BTC-USD",
        cohort="crypto_24h",
        horizon_minutes=15,
        posted_at=at,
        entry_at=dt("2021-02-01T12:01:00Z"),
        entry_delay_seconds=30,
        forward_return=0.1,
        benchmark_adjusted_return=None,
        volume=300,
        trade_count=60,
        realized_volatility=0.02,
    )
    blocked = dt("2021-01-25T12:00:30Z")
    posts = [SimpleNamespace(created_at=t) for t in [at, blocked]]
    settings = {
        **SETTINGS,
        "control_start": "2020-01-01",
        "candidate_prior_days_or_sessions": 60,
        "minimum_candidate_pool": 10,
        "matched_controls": 5,
        "minimum_matched_controls": 3,
        "rms_caliper": 2.0,
    }
    result = matched_placebos([event], posts, Store(), clock, {"BTC-USD": "BTC-USD"}, settings)
    assert len(result["records"]) == 1
    record = result["records"][0]
    assert len(record["controls"]) == 5
    for control in record["controls"]:
        entry = dt(control["entry"])
        assert entry + timedelta(minutes=15) < at
        assert entry.date() != blocked.date()
        assert dt(control["features_end"]) == entry - timedelta(minutes=6)
        assert control["distance"] == 0
    assert record["effects"]["return_difference"] == 0.1
    assert record["effects"]["volume_ratio"] == 2
    assert all(r["p"] is None for r in result["summaries"])
