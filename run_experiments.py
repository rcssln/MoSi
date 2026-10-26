"""run_experiments.py - run every scenario for several independent replications."""
import os
import pandas as pd
import config
from terminal_model import run_simulation


def run_all(replications=config.REPLICATIONS):
    rows = []
    for sc in config.SCENARIOS:
        params = {**config.BASE_PARAMS, **sc}
        for rep in range(replications):
            # Same seed for the same replication number in every scenario, so
            # scenarios see similar random numbers (helps the paired comparison).
            seed = config.SEED_BASE + rep
            res = run_simulation(params, seed)
            rows.append({"scenario": sc["name"], "period": sc["period"],
                         "fleet_size": sc["fleet_size"], "rule": sc["rule"],
                         "time_limit": sc["time_limit"], "replication": rep,
                         "seed": seed, **res})
        print(f"done {sc['name']}")
    return pd.DataFrame(rows)


if __name__ == "__main__":
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    df = run_all()
    path = os.path.join(config.OUTPUT_DIR, "results.csv")
    df.to_csv(path, index=False)
    print(f"saved {len(df)} rows to {path}")
