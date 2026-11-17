"""Render validation diagnostics and an individual price path for each eligible post."""

import json

import numpy as np

from musk_sentiment.utils.io import write_json


def plot_validation(folder):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    profiles = json.loads((folder / "event_profiles.json").read_text())
    influence = json.loads((folder / "influence.json").read_text())["summaries"]
    placebos = json.loads((folder / "matched_placebos.json").read_text())["summaries"]
    files = []
    for summary in profiles["summaries"]:
        ticker, cohort = summary["ticker"], summary["cohort"]
        paths = [p for p in profiles["paths"] if p["ticker"] == ticker and p["cohort"] == cohort]
        delayed = cohort == "next_opening"
        if delayed:
            fig, axis = plt.subplots(figsize=(9, 4.5))
            axes = [axis]
        else:
            fig, panel = plt.subplots(2, 2, figsize=(11, 8))
            axes = list(panel.flat)
        ax = axes[0]
        for p in paths:
            ax.plot(
                p["offset_minutes"],
                np.array(p["cumulative_return"]) * 100,
                color="0.7",
                alpha=0.3,
                linewidth=0.7,
            )
        x = summary["offset_minutes"]
        ax.plot(
            x,
            np.array(summary["mean_path"]) * 100,
            color="#285b8a",
            linewidth=2,
            label="Equal-day mean",
        )
        if summary["ci_low"] is not None:
            ax.fill_between(
                x,
                np.array(summary["ci_low"]) * 100,
                np.array(summary["ci_high"]) * 100,
                color="#285b8a",
                alpha=0.18,
                label="Pointwise 95% interval",
            )
        ax.axhline(0, color="black", linewidth=0.6)
        ax.axvspan(0, 1, color="#aa7733", alpha=0.15)
        ax.set(
            ylabel="Cumulative price change (%)",
            xlabel="Minutes from opening" if delayed else "Minutes from publication-minute start",
            title="Individual traces and day-cluster average",
        )
        ax.legend(fontsize=8)
        if not delayed:
            for ax, metric, title in zip(
                axes[1:],
                ["volume_rate_ratio", "trade_count_rate_ratio", "volatility_rate_ratio"],
                ["Volume per minute", "Trades per minute", "Volatility per sqrt(minute)"],
                strict=True,
            ):
                bins = summary["activity_bins"]
                x = [(r["start"] + r["end"]) / 2 for r in bins]
                y = [r[metric]["mean"] for r in bins]
                ax.plot(x, y, "o-", color="#285b8a")
                for at, r in zip(x, bins, strict=True):
                    ci = r[metric]["ci"]
                    if ci:
                        ax.vlines(at, ci[0], ci[1], color="#285b8a", alpha=0.5)
                ax.axhline(1, color="black", linewidth=0.6, linestyle="--")
                ax.axvspan(0, 1, color="#aa7733", alpha=0.15)
                ax.set(
                    title=title,
                    xlabel="Minutes from publication-minute start",
                    ylabel="Ratio to own −30 to −5 minute rate",
                )
        fig.suptitle(
            f"{ticker} | {cohort.replace('_', ' ')} | "
            f"{summary['events']} posts, {summary['days']} days"
        )
        note = (
            "Delayed opening response: no pre-publication price path is inferred."
            if delayed
            else "Complete −30/+60-minute subset. Publication is within shaded minute [0,1)."
        )
        fig.text(
            0.5,
            0.015,
            note + "\nExploratory association. Intervals are pointwise and unadjusted.",
            ha="center",
            fontsize=8,
        )
        fig.tight_layout(rect=(0, 0.065, 1, 0.95))
        path = folder / f"profile_{ticker}_{cohort}.png"
        fig.savefig(path, dpi=160)
        plt.close(fig)
        files.append(str(path))
    individual_dir = folder / "individual_profiles"
    individual_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for p in profiles["paths"]:
        fig, ax = plt.subplots(figsize=(7, 3.4))
        ax.plot(p["offset_minutes"], np.array(p["cumulative_return"]) * 100, color="#285b8a")
        ax.axhline(0, color="black", linewidth=0.6)
        ax.axvspan(0, 1, color="#aa7733", alpha=0.15)
        label = (
            "Minutes after next opening (delayed)"
            if p["cohort"] == "next_opening"
            else "Minutes from publication-minute start"
        )
        ax.set(
            title=f"{p['ticker']} | {p['post_id']}\n{p['posted_at']} | {p['cohort']}",
            xlabel=label,
            ylabel="Price change (%)",
        )
        fig.tight_layout()
        path = individual_dir / f"{p['ticker']}_{p['post_id']}.png"
        fig.savefig(path, dpi=130)
        plt.close(fig)
        index.append({"ticker": p["ticker"], "post_id": p["post_id"], "path": str(path)})
    # Matched controls: explicitly show suppressed intervals for small independent samples.
    rows = [
        r for r in placebos if r["horizon_minutes"] == 15 and r["metric"] == "return_difference"
    ]
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, r in enumerate(rows):
        ax.plot(r["component_mean"] * 100, i, "o", color="#285b8a")
        if r["ci"]:
            ax.hlines(i, r["ci"][0] * 100, r["ci"][1] * 100, color="#285b8a")
        ax.text(
            0.99,
            i + 0.18,
            f"n={r['events']}; components={r['independent_components']}"
            + ("; no inference" if r["ci"] is None else ""),
            transform=ax.get_yaxis_transform(),
            ha="right",
            fontsize=8,
        )
    ax.set_ylim(-0.5, len(rows) - 0.35)
    ax.set_yticks(range(len(rows)), [r["ticker"] + " / " + r["cohort"] for r in rows])
    ax.axvline(0, color="black", linewidth=0.6)
    ax.set(
        xlabel="Post minus matched-control return (percentage points)",
        title=(
            "15-minute matched-placebo diagnostic\n"
            "Shared-control dependence reduces independent sample size"
        ),
    )
    fig.tight_layout()
    path = folder / "matched_placebo_15m.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    files.append(str(path))
    for ticker in ["DOGE-USD", "TSLA"]:
        rows = [
            r
            for r in influence
            if r["ticker"] == ticker
            and r["horizon_minutes"] == 15
            and r["metric"] == "forward_return"
            and r["leave_one_day_out"]
        ]
        if not rows:
            continue
        fig, panels = plt.subplots(len(rows), 1, figsize=(10, 3.5 * len(rows)), squeeze=False)
        for ax, r in zip(panels.flat, rows, strict=True):
            dates = sorted(r["leave_one_day_out"])
            ax.plot(
                range(len(dates)),
                [r["leave_one_day_out"][d] * 100 for d in dates],
                "o",
                color="#285b8a",
                markersize=4,
            )
            ax.axhline(r["mean_day"] * 100, color="0.4", linestyle="--", label="All-day mean")
            ax.axhline(0, color="black", linewidth=0.6)
            ax.set_xticks(
                range(0, len(dates), max(1, len(dates) // 10)),
                dates[:: max(1, len(dates) // 10)],
                rotation=45,
                ha="right",
            )
            ax.set(
                title=f"{ticker} / {r['cohort']}: drop one entire day",
                xlabel="Omitted day",
                ylabel="Remaining mean return (%)",
            )
            ax.legend(fontsize=8)
        fig.tight_layout()
        path = folder / f"leave_one_day_out_{ticker}.png"
        fig.savefig(path, dpi=160)
        plt.close(fig)
        files.append(str(path))
    write_json(folder / "figures.json", {"summary_figures": files, "individual_profiles": index})
    return {"summary_figures": files, "individual_profile_count": len(index)}
