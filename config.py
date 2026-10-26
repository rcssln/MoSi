"""config.py - every parameter and the scenario list live here.

Values marked ASSUMPTION have NOT been measured. Replace them with your own
data (fit_inputs.py prints suggested replacements) before reporting results.
Time units: minutes everywhere, except boarding time which is in seconds.

Terminal modeled: Laoag City terminal. Route: Laoag City - Batac City - Paoay,
driven as a full round trip back to Laoag (one route, treated as one line;
passengers are not split by destination).
"""

# ---------------- Experiment settings ----------------
SEED_BASE = 2025        # replication r uses seed SEED_BASE + r
REPLICATIONS = 30       # independent replications per scenario
WARMUP_MIN = 60         # ASSUMPTION: statistics are discarded before this time
RUN_LENGTH_MIN = 480    # ASSUMPTION: 8 hours of measured time after the warm-up
OUTPUT_DIR = "outputs"

# ---------------- System parameters ----------------
CAPACITY = 20           # reported by project owner: about 20 passengers when full (C)

# Passenger inter-arrival time: Exponential, mean in minutes
ARRIVAL_MEAN_MIN = {
    "peak": 0.5,        # ASSUMPTION: one passenger every 0.5 min
    "offpeak": 1.5,     # ASSUMPTION: one passenger every 1.5 min
}

# Boarding time per passenger: Normal, truncated at a small positive minimum
BOARD_MEAN_SEC = 6.0    # ASSUMPTION
BOARD_SD_SEC = 2.0      # ASSUMPTION
BOARD_MIN_SEC = 1.0     # ASSUMPTION: truncation point

# Round-trip time: Normal, truncated at a small positive minimum
TRIP_MEAN_MIN = 40.0    # ASSUMPTION
TRIP_SD_MIN = 6.0       # ASSUMPTION
TRIP_MIN_MIN = 5.0      # ASSUMPTION: truncation point

# Initial fleet: all N jeepneys line up at the terminal at time 0
FLEET_SIZES = [6, 8]    # ASSUMPTION: values of N to test

# Timed-rule limits to test (minutes since the jeepney entered the bay)
TIME_LIMITS = [5, 10, 15]

# Base parameters handed to the model (scenario values are added on top)
BASE_PARAMS = {
    "capacity": CAPACITY,
    "warmup": WARMUP_MIN,
    "run_length": RUN_LENGTH_MIN,
    "board_mean_sec": BOARD_MEAN_SEC,
    "board_sd_sec": BOARD_SD_SEC,
    "board_min_sec": BOARD_MIN_SEC,
    "trip_mean": TRIP_MEAN_MIN,
    "trip_sd": TRIP_SD_MIN,
    "trip_min": TRIP_MIN_MIN,
}


def build_scenarios():
    """One dict per scenario: peak/off-peak x fleet size x dispatch rule."""
    scenarios = []
    for period, mean_gap in ARRIVAL_MEAN_MIN.items():
        for n in FLEET_SIZES:
            common = {"period": period, "fleet_size": n, "mean_interarrival": mean_gap}
            scenarios.append({"name": f"{period}_N{n}_baseline", "rule": "baseline",
                              "time_limit": None, **common})
            for t in TIME_LIMITS:
                scenarios.append({"name": f"{period}_N{n}_timed{t}", "rule": "timed",
                                  "time_limit": t, **common})
    return scenarios


SCENARIOS = build_scenarios()

# ---------------- Validation ----------------
# Fill in values you observed at the real terminal (None = not provided).
# "scenario" must match one name in SCENARIOS, e.g. "peak_N6_baseline".
OBSERVED = {
    "scenario": "peak_N6_timed10",   # real terminal currently uses T = 10 min
    "avg_wait": None,    # minutes
    "avg_seats": None,   # passengers per departure
}
