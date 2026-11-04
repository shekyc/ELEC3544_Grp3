"""Small tested primitives; production event study construction is a later milestone."""

import math


def simple_return(before: float, after: float) -> float:
    if not all(math.isfinite(p) and p > 0 for p in (before, after)):
        raise ValueError("Prices must be finite and positive")
    return after / before - 1


def benchmark_adjusted(asset_return: float, benchmark_return: float) -> float:
    if not all(math.isfinite(v) for v in (asset_return, benchmark_return)):
        raise ValueError("Returns must be finite")
    return asset_return - benchmark_return
