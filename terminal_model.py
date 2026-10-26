# terminal_model.py - SimPy model of one jeepney terminal (one loading bay, one waiting line).
# Passengers arrive at random and join a single first-come, first-served line. Jeepneys
# queue for the one loading bay, load passengers until the dispatch rule says to depart,
# make a random round trip, and rejoin the queue. All times are in minutes. Statistics
# are recorded only after the warm-up period.

import numpy as np
import simpy

# Stores the time a passenger joined the line and an event that is triggered when a
# jeepney takes the passenger from the line.
class Passenger:
    def __init__(self, env, arrival_time):
        self.arrival_time = arrival_time
        self.boarded = env.event()

# Holds the whole system: the passenger line, the loading bay, the random samplers,
# and every counter used for the results. A test can replace any sampler with fixed
# values. The whole-run counters (arrived, left_line) are used for the conservation check;
# the lists and sums below them are recorded after the warm-up only.
class Terminal:
    def __init__(self, env, params, rng, log=False):
        self.env = env
        self.p = params
        self.rng = rng
        self.line = simpy.Store(env)
        self.bay = simpy.Resource(env, capacity=1)
        self.warmup = params["warmup"]

        self.next_gap = params.get("arrival_sampler") or (
            lambda: rng.exponential(params["mean_interarrival"]))
        self.next_board = params.get("board_sampler") or (
            lambda: max(params["board_min_sec"],
                        rng.normal(params["board_mean_sec"], params["board_sd_sec"])) / 60)
        self.next_trip = params.get("trip_sampler") or (
            lambda: max(params["trip_min"],
                        rng.normal(params["trip_mean"], params["trip_sd"])))

        self.arrived = 0
        self.left_line = 0
        self.waits = []
        self.depart_waits = []
        self.seats = []
        self.idles = []
        self.area = 0.0
        self.last_t = 0.0
        self.bay_busy = 0.0
        self.bay_since = None
        self.log_lines = [] if log else None

    # Adds one line "time  event" to the event log. Does nothing when logging is off.
    def log(self, text):
        if self.log_lines is not None:
            self.log_lines.append(f"{self.env.now:8.2f}  {text}")

    # Keeps the running total of (line length x time) used to compute the average number
    # of passengers waiting. Must be called just before the line length changes. Time
    # inside the warm-up period is not counted.
    def track(self):
        now = self.env.now
        start = max(self.last_t, self.warmup)
        if now > start:
            self.area += len(self.line.items) * (now - start)
        self.last_t = now

    # Runs for the whole simulation. After each random inter-arrival time (Exponential),
    # it creates one new passenger process.
    def passenger_generator(self):
        while True:
            yield self.env.timeout(self.next_gap())
            self.env.process(self.passenger())

    # One passenger. Joins the back of the waiting line, then stays until load() takes
    # them from the front of the line.
    def passenger(self):
        pax = Passenger(self.env, self.env.now)
        self.arrived += 1
        self.track()
        self.line.put(pax)
        self.log(f"passenger arrives (line = {len(self.line.items)})")
        yield pax.boarded

    # Loads the jeepney that is in the bay and returns the passengers on board. Each
    # passenger takes a random boarding time. Departure rules:
    # baseline - depart only when all seats are full
    # timed    - depart when full, or when the time limit has passed since the jeepney
    # entered the bay; a jeepney with nobody on board keeps waiting for its
    # first passenger instead of leaving empty
    def load(self):
        env, cap = self.env, self.p["capacity"]
        timed = self.p["rule"] == "timed"
        deadline = env.now + self.p["time_limit"] if timed else None
        onboard = []
        while len(onboard) < cap:
            if timed and env.now >= deadline and len(onboard) >= 1:
                break
            self.track()
            get = self.line.get()
            if timed and env.now < deadline:
                yield get | env.timeout(deadline - env.now)
                if not get.triggered:
                    get.cancel()
                    continue
            else:
                yield get
            pax = get.value
            self.left_line += 1
            if env.now >= self.warmup:
                self.waits.append(env.now - pax.arrival_time)
            pax.boarded.succeed()
            onboard.append(pax)
            self.log(f"passenger boards (seat {len(onboard)}/{cap})")
            yield env.timeout(self.next_board())
        return onboard

    # Life cycle of one jeepney, repeated forever: join the jeepney queue, enter the bay
    # when it is free, load, depart, travel for a random round-trip time, then rejoin the
    # queue. At each departure after the warm-up it records the seats filled, the time
    # spent at the terminal (including waiting for the bay), and each passenger's time
    # from arrival to departure.
    def jeepney(self, jid):
        env = self.env
        while True:
            arrive = env.now
            self.log(f"jeepney {jid} arrives at terminal")
            with self.bay.request() as req:
                yield req
                bay_enter = env.now
                self.bay_since = bay_enter
                self.log(f"jeepney {jid} enters bay")
                onboard = yield from self.load()
                seats = len(onboard)
                self.bay_busy += max(0.0, env.now - max(bay_enter, self.warmup))
                self.bay_since = None
                if env.now >= self.warmup:
                    self.seats.append(seats)
                    self.idles.append(env.now - arrive)
                    self.depart_waits += [env.now - pax.arrival_time for pax in onboard]
                self.log(f"jeepney {jid} departs with {seats} passengers")
            yield env.timeout(self.next_trip())

    # Converts the recorded values into the performance measures of one replication:
    # average and maximum wait in line, average and maximum time from arrival to
    # departure, average passengers waiting, jeepney idle time per trip, bay utilization
    # (fraction of time occupied), passengers served per hour, and seats filled per
    # departure. Measures with no data are returned as nan. The whole-run counts are
    # included so the conservation check can be made.
    def results(self, end):
        self.track()
        if self.bay_since is not None:
            self.bay_busy += end - max(self.bay_since, self.warmup)
        measured = end - self.warmup
        mean = lambda x: float(np.mean(x)) if len(x) else float("nan")
        out = {
            "avg_wait": mean(self.waits),
            "max_wait": max(self.waits) if self.waits else float("nan"),
            "avg_depart_wait": mean(self.depart_waits),
            "max_depart_wait": max(self.depart_waits) if self.depart_waits else float("nan"),
            "avg_waiting": self.area / measured,
            "avg_idle": mean(self.idles),
            "bay_util": self.bay_busy / measured,
            "served_per_hour": len(self.waits) / (measured / 60),
            "avg_seats": mean(self.seats),
            "departures": len(self.seats),
            "arrived": self.arrived,
            "boarded": self.left_line,
            "still_waiting": len(self.line.items),
        }
        if self.log_lines is not None:
            out["log"] = self.log_lines
        return out

# Runs one replication: builds the terminal, starts the passenger arrivals and all
# jeepneys (every jeepney starts in the queue at time 0), runs for the warm-up plus the
# measured period, and returns the performance measures. The same seed always gives the
# same result.
def run_simulation(params, seed, log=False):
    env = simpy.Environment()
    rng = np.random.default_rng(seed)
    term = Terminal(env, params, rng, log)
    env.process(term.passenger_generator())
    for jid in range(params["fleet_size"]):
        env.process(term.jeepney(jid))
    end = params["warmup"] + params["run_length"]
    env.run(until=end)
    return term.results(end)