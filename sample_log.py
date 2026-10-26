"""sample_log.py - prints a short event log of a tiny run, for the Sample Outputs slide.

Setup (same as the hand-calculated test): capacity 2, one jeepney, a passenger every
1 minute, boarding 0.5 min, round trip 10 min. Run: python sample_log.py
"""
import config
from terminal_model import run_simulation

params = {**config.BASE_PARAMS, "rule": "baseline", "time_limit": None, "fleet_size": 1,
          "mean_interarrival": 1.0, "trip_mean": 10.0, "capacity": 2, "warmup": 0,
          "run_length": 14,
          "arrival_sampler": lambda: 1.0, "board_sampler": lambda: 0.5,
          "trip_sampler": lambda: 10.0}

result = run_simulation(params, seed=1, log=True)
print("time (min)  event")
for line in result["log"]:
    print(line)
