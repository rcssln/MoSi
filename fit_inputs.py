"""fit_inputs.py - fit Exponential / Normal / Erlang to your collected data.

Usage:  python fit_inputs.py my_data.csv

CSV columns: event_type, and a number in a column named timestamp OR duration.
  event_type        number                                   unit
  passenger_arrival timestamp of each arrival (inter-arrivals are computed)  min
  jeepney_arrival   timestamp of each arrival (inter-arrivals are computed)  min
  boarding          duration per passenger                    sec
  round_trip        duration                                  min
"""
import json
import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
import config

# event_type -> (is_timestamp, unit, label)
EVENTS = {
    "passenger_arrival": (True, "min", "Passenger inter-arrival time"),
    "jeepney_arrival": (True, "min", "Jeepney inter-arrival time"),
    "boarding": (False, "sec", "Boarding time per passenger"),
    "round_trip": (False, "min", "Round-trip time"),
}


def load_samples(path):
    if not os.path.exists(path):
        sys.exit(f"File not found: {path}\n"
                 "'my_data.csv' was only an example name. Pass the path to your own data file; "
                 "see data_template.csv for the expected columns.")
    df = pd.read_csv(path)
    cols = [c for c in ("timestamp", "duration", "value") if c in df.columns]
    df["x"] = df[cols].bfill(axis=1).iloc[:, 0]
    samples = {}
    for event, (is_ts, _, _) in EVENTS.items():
        x = df.loc[df.event_type == event, "x"].dropna().to_numpy(float)
        if is_ts:
            x = np.diff(np.sort(x))          # timestamps -> gaps between events
        if len(x) >= 5:
            samples[event] = x
    return samples


def fit_candidates(x):
    """Return {name: frozen scipy distribution}."""
    mean = x.mean()
    cands = {}      # order = plot order
    mu, sd = stats.norm.fit(x)
    cands["normal"] = stats.norm(mu, sd)
    if x.min() > 0:                          # Exponential/Erlang need positive data
        cands["exponential"] = stats.expon(loc=0, scale=mean)
        shape, _, _ = stats.gamma.fit(x, floc=0)
        k = max(1, int(round(shape)))        # Erlang = gamma with integer shape
        cands["erlang"] = stats.erlang(a=k, scale=mean / k)
    else:
        print("   (non-positive values found: skipping Exponential and Erlang)")
    return cands


def describe(name, dist):
    if name == "exponential":
        return {"mean": float(dist.kwds["scale"])}
    if name == "normal":
        return {"mean": float(dist.mean()), "sd": float(dist.std())}
    k = dist.args[0] if dist.args else dist.kwds["a"]
    return {"k": int(k), "scale": float(dist.kwds["scale"])}


def fit_and_plot(event, x, outdir):
    _, unit, label = EVENTS[event]
    cands = fit_candidates(x)
    report = {"n": len(x), "sample_mean": float(x.mean()), "sample_sd": float(x.std(ddof=1)),
              "fits": {}}
    fig, axes = plt.subplots(1, 1 + len(cands), figsize=(4.5 * (1 + len(cands)), 4))
    axes[0].hist(x, bins="auto", density=True, alpha=0.5, label="data")
    grid = np.linspace(x.min(), x.max(), 200)
    p = (np.arange(1, len(x) + 1) - 0.5) / len(x)
    for ax, (name, dist) in zip(axes[1:], cands.items()):
        ks = stats.kstest(x, dist.cdf)       # note: p-value is optimistic for fitted params
        report["fits"][name] = {**describe(name, dist), "ks_stat": float(ks.statistic),
                                "ks_p": float(ks.pvalue)}
        axes[0].plot(grid, dist.pdf(grid), label=name)
        ax.scatter(dist.ppf(p), np.sort(x), s=8)
        lim = [min(x.min(), dist.ppf(p).min()), max(x.max(), dist.ppf(p).max())]
        ax.plot(lim, lim, "r--")
        ax.set_title(f"Q-Q plot: {name} (KS p={ks.pvalue:.3f})")
        ax.set_xlabel(f"Theoretical quantiles ({unit})")
        ax.set_ylabel(f"Sample quantiles ({unit})")
    axes[0].set_title(f"{label}: histogram + fits")
    axes[0].set_xlabel(f"Time ({unit})")
    axes[0].set_ylabel("Density")
    axes[0].legend()
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, f"fit_{event}.png"), dpi=150)
    plt.close(fig)
    report["best_by_ks"] = min(report["fits"], key=lambda k: report["fits"][k]["ks_stat"])
    return report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python fit_inputs.py my_data.csv")
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    result = {}
    for event, x in load_samples(sys.argv[1]).items():
        result[event] = fit_and_plot(event, x, config.OUTPUT_DIR)
        print(f"{event}: n={len(x)}, best fit by KS = {result[event]['best_by_ks']}")
        for name, f in result[event]["fits"].items():
            print(f"   {name:12s} {f}")
    path = os.path.join(config.OUTPUT_DIR, "fitted_params.json")
    with open(path, "w") as fh:
        json.dump(result, fh, indent=2)
    print(f"saved fitted parameters to {path}; copy the chosen values into config.py")
