"""sensitivity.py - where does each dispatch rule stop working well?

Sweep 1: passenger arrival rate (passengers per minute), fleet size fixed.
Sweep 2: fleet size N, arrival rate fixed at the peak value.
Both compare the baseline rule with the timed rule (T = first value in config.TIME_LIMITS).
Uses the PEAK round-trip time from config. Results go to outputs/sensitivity_*.csv.
"""
import os
import pandas as pd
import config
from terminal_model import run_simulation

RATES_PER_MIN = [0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 8]    # passengers per minute
FLEET_SWEEP = [6, 8, 10, 12, 15, 18, 20]
REPS = config.REPLICATIONS
T = config.TIME_LIMITS[0]


def one_setting(rule, fleet_size, mean_gap, reps=REPS):
    rows = []
    for rep in range(reps):
        p = {**config.BASE_PARAMS, "rule": rule, "time_limit": T if rule == "timed" else None,
             "fleet_size": fleet_size, "mean_interarrival": mean_gap,
             "trip_mean": config.TRIP_MEAN_MIN["peak"]}
        rows.append(run_simulation(p, config.SEED_BASE + rep))
    return pd.DataFrame(rows).mean(numeric_only=True)


def sweep(values, make_args, label):
    out = []
    for v in values:
        for rule in ("baseline", "timed"):
            res = one_setting(rule, *make_args(v))
            out.append({label: v, "rule": rule, **res.to_dict()})
        print(f"done {label} = {v}")
    return pd.DataFrame(out)


if __name__ == "__main__":
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    n = config.FLEET_SIZES[0]
    peak_gap = config.ARRIVAL_MEAN_MIN["peak"]
    a = sweep(RATES_PER_MIN, lambda r: (n, 1 / r), "arrival_per_min")
    a.to_csv(os.path.join(config.OUTPUT_DIR, "sensitivity_arrival.csv"), index=False)
    f = sweep(FLEET_SWEEP, lambda k: (k, peak_gap), "fleet_size")
    f.to_csv(os.path.join(config.OUTPUT_DIR, "sensitivity_fleet.csv"), index=False)
    print("saved sensitivity_arrival.csv and sensitivity_fleet.csv")
