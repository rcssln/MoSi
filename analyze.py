"""analyze.py - confidence intervals, comparison with baseline, charts, validation."""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
import config

MEASURES = {   # column -> label with units
    "avg_wait": "Average passenger wait in line (min)",
    "max_wait": "Maximum passenger wait (min)",
    "avg_depart_wait": "Average time from arrival to departure (min)",
    "max_depart_wait": "Maximum time from arrival to departure (min)",
    "avg_waiting": "Average passengers waiting (people)",
    "avg_idle": "Jeepney time at terminal per trip (min)",
    "bay_util": "Bay utilization (fraction)",
    "served_per_hour": "Passengers served (per hour)",
    "avg_seats": "Seats filled per departure (people)",
}
OUT = config.OUTPUT_DIR


def ci(x, level=0.95):
    """Mean and half-width of the t confidence interval."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    half = stats.t.ppf((1 + level) / 2, n - 1) * x.std(ddof=1) / np.sqrt(n)
    return x.mean(), half


def summarize(df):
    rows = []
    for name, g in df.groupby("scenario", sort=False):
        row = {"scenario": name, **{k: g[k].iloc[0] for k in
               ("period", "fleet_size", "rule", "time_limit")}}
        for m in MEASURES:
            row[m + "_mean"], row[m + "_hw"] = ci(g[m])
        rows.append(row)
    return pd.DataFrame(rows)


def compare_to_baseline(df):
    """Paired difference (timed - baseline) per replication, with 95% CI."""
    rows = []
    for _, sc in df.drop_duplicates("scenario").iterrows():
        if sc["rule"] == "baseline":
            continue
        base_name = f"{sc['period']}_N{sc['fleet_size']}_baseline"
        a = df[df.scenario == sc["scenario"]].set_index("replication")
        b = df[df.scenario == base_name].set_index("replication")
        row = {"scenario": sc["scenario"], "baseline": base_name}
        for m in MEASURES:
            mean, half = ci(a[m] - b[m])
            row[m + "_diff"], row[m + "_hw"] = mean, half
            row[m + "_signif"] = abs(mean) > half      # CI excludes 0
        rows.append(row)
    return pd.DataFrame(rows)


def plot_vs_T(summ, measure, fname):
    """Measure vs time limit T, one line per (period, N); dashed = baseline."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for (period, n), g in summ.groupby(["period", "fleet_size"]):
        t = g[g.rule == "timed"].sort_values("time_limit")
        line = ax.errorbar(t.time_limit, t[measure + "_mean"], yerr=t[measure + "_hw"],
                           marker="o", capsize=3, label=f"{period}, N={n}")
        base = g[g.rule == "baseline"][measure + "_mean"].iloc[0]
        ax.axhline(base, ls="--", lw=1, color=line[0].get_color())
    ax.set_xlabel("Time limit T (min)")
    ax.set_ylabel(MEASURES[measure])
    ax.set_title(f"{MEASURES[measure]} vs. time limit T\n(dashed = baseline, bars = 95% CI)")
    ax.set_xticks(config.TIME_LIMITS)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, fname), dpi=150)
    plt.close(fig)


def plot_scenarios(summ, measure, fname):
    """Bar chart comparing all scenarios on one measure."""
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(summ.scenario, summ[measure + "_mean"], xerr=summ[measure + "_hw"], capsize=3)
    ax.set_xlabel(MEASURES[measure])
    ax.set_ylabel("Scenario")
    ax.set_title(f"{MEASURES[measure]} by scenario (95% CI)")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, fname), dpi=150)
    plt.close(fig)


def validate(scenario, observed_avg_wait, observed_avg_seats, results_csv=None):
    """Is each observed value inside the simulated 95% CI? Returns a dict of results."""
    df = pd.read_csv(results_csv or os.path.join(OUT, "results.csv"))
    g = df[df.scenario == scenario]
    out = {}
    for label, col, obs in (("avg wait (min)", "avg_wait", observed_avg_wait),
                            ("seats per departure", "avg_seats", observed_avg_seats)):
        if obs is None:
            continue
        mean, half = ci(g[col])
        inside = mean - half <= obs <= mean + half
        print(f"{scenario} {label}: observed {obs:.2f}, simulated "
              f"{mean:.2f} [{mean - half:.2f}, {mean + half:.2f}] -> "
              f"{'INSIDE' if inside else 'OUTSIDE'} the 95% CI")
        out[col] = inside
    return out


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    df = pd.read_csv(os.path.join(OUT, "results.csv"))
    summ = summarize(df)
    summ.to_csv(os.path.join(OUT, "summary.csv"), index=False)
    diff = compare_to_baseline(df)
    diff.to_csv(os.path.join(OUT, "diff_vs_baseline.csv"), index=False)
    if len(config.TIME_LIMITS) > 1:       # a line chart needs more than one T value
        plot_vs_T(summ, "avg_wait", "wait_vs_T.png")
        plot_vs_T(summ, "avg_idle", "idle_vs_T.png")
    plot_scenarios(summ, "avg_wait", "scenarios_avg_wait.png")
    plot_scenarios(summ, "served_per_hour", "scenarios_served.png")
    print(summ[["scenario", "avg_wait_mean", "avg_wait_hw", "avg_idle_mean",
                "bay_util_mean", "avg_seats_mean"]].round(2).to_string(index=False))
    obs = config.OBSERVED
    if obs["avg_wait"] is not None or obs["avg_seats"] is not None:
        validate(obs["scenario"], obs["avg_wait"], obs["avg_seats"])
    else:
        print("\nValidation skipped: fill config.OBSERVED with your observed values.")
