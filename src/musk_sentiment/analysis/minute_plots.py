"""Scientific summary figures from saved minute results; no model fitting in plotting."""

import json


def plot_minutes(folder):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = json.loads((folder / "day_cluster_sensitivity.json").read_text())["summaries"]
    groups = [
        ("TSLA", "regular", "TSLA regular", "#3366aa", "o"),
        ("TSLA", "next_opening", "TSLA next opening", "#777777", "s"),
        ("DOGE-USD", "crypto_24h", "DOGE", "#bb6611", "^"),
        ("BTC-USD", "crypto_24h", "BTC", "#228855", "D"),
    ]
    metrics = [
        ("forward_return", "Forward price return", "Return (%)", 100),
        ("relative_volume", "Trading volume", "Times historical reference", 1),
        ("relative_trade_count", "Number of trades", "Times historical reference", 1),
        ("relative_volatility", "Realized volatility", "Times historical reference", 1),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    for ax, (metric, title, ylabel, scale) in zip(axes.flat, metrics, strict=True):
        for number, (ticker, cohort, label, color, marker) in enumerate(groups):
            rows = sorted(
                [
                    r
                    for r in data
                    if r["ticker"] == ticker and r["cohort"] == cohort and r["metric"] == metric
                ],
                key=lambda r: r["horizon_minutes"],
            )
            x = [r["horizon_minutes"] + (number - 1.5) * 0.55 for r in rows]
            y = [r["equal_cluster_mean"] * scale for r in rows]
            ax.plot(x, y, marker=marker, color=color, label=label, linewidth=1)
            for at, row in zip(x, rows, strict=True):
                ci = row["cluster_bootstrap_95ci"]
                if ci:
                    ax.vlines(at, ci[0] * scale, ci[1] * scale, color=color, alpha=0.65)
        ax.axhline(
            0 if metric == "forward_return" else 1, color="black", linewidth=0.7, linestyle="--"
        )
        ax.set(title=title, xlabel="Window length (minutes)", ylabel=ylabel, xticks=[5, 15, 30])
        if metric != "forward_return":
            ax.set_yscale("log")
            ax.set_yticks([1, 2, 5, 10, 20], ["1", "2", "5", "10", "20"])
        ax.spines[["top", "right"]].set_visible(False)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 0.945))
    fig.suptitle("2020–2021 V7: minute-level price and trading activity", fontsize=15)
    fig.text(
        0.5,
        0.025,
        (
            "Day-cluster means and unadjusted 95% bootstrap intervals. "
            "Exploratory associations, not causal effects.\n"
            "Activity references use earlier comparable windows; eligible sample sizes differ. "
            "Next-opening is delayed, not immediate."
        ),
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.08, 1, 0.91))
    path = folder / "minute_outcomes.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return {"figures": [str(path)]}
