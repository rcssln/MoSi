"""terminal_model.py - SimPy model of one jeepney terminal.

Processes: passenger_generator -> passenger (one per person) and jeepney (one per vehicle).
Times are in minutes. Statistics are only recorded after the warm-up period.
"""
import numpy as np
import simpy


class Passenger:
    def __init__(self, env, arrival_time):
        self.arrival_time = arrival_time
        self.boarded = env.event()          # fired when the passenger leaves the line


class Terminal:
    def __init__(self, env, params, rng, log=False):
        self.env = env
        self.p = params
        self.rng = rng
        self.line = simpy.Store(env)                    # single FCFS waiting line
        self.bay = simpy.Resource(env, capacity=1)      # one loading bay
        self.warmup = params["warmup"]

        # Samplers. Tests can override them with fixed sequences.
        self.next_gap = params.get("arrival_sampler") or (
            lambda: rng.exponential(params["mean_interarrival"]))
        self.next_board = params.get("board_sampler") or (
            lambda: max(params["board_min_sec"],
                        rng.normal(params["board_mean_sec"], params["board_sd_sec"])) / 60)
        self.next_trip = params.get("trip_sampler") or (
            lambda: max(params["trip_min"],
                        rng.normal(params["trip_mean"], params["trip_sd"])))

        # Counters over the WHOLE run (used for the conservation check)
        self.arrived = 0
        self.left_line = 0
        # Statistics after warm-up only
        self.waits = []          # one value per boarded passenger (min)
        self.seats = []          # passengers on board at each departure
        self.idles = []          # time at terminal per trip (min)
        self.area = 0.0          # integral of queue length over time
        self.last_t = 0.0
        self.bay_busy = 0.0      # time the bay was occupied
        self.bay_since = None    # when the current jeepney entered the bay
        self.log_lines = [] if log else None

    def log(self, text):
        if self.log_lines is not None:
            self.log_lines.append(f"{self.env.now:8.2f}  {text}")

    def track(self):
        """Call BEFORE the line length changes: adds length x elapsed time to the area."""
        now = self.env.now
        start = max(self.last_t, self.warmup)
        if now > start:
            self.area += len(self.line.items) * (now - start)
        self.last_t = now

    # ---------- processes ----------
    def passenger_generator(self):
        while True:
            yield self.env.timeout(self.next_gap())
            self.env.process(self.passenger())

    def passenger(self):
        pax = Passenger(self.env, self.env.now)
        self.arrived += 1
        self.track()
        self.line.put(pax)
        self.log(f"passenger arrives (line = {len(self.line.items)})")
        yield pax.boarded                   # waits until a jeepney takes them

    def load(self):
        """Load passengers into the jeepney in the bay; returns number on board."""
        env, cap = self.env, self.p["capacity"]
        timed = self.p["rule"] == "timed"
        deadline = env.now + self.p["time_limit"] if timed else None
        seats = 0
        while seats < cap:
            if timed and env.now >= deadline and seats >= 1:
                break                                   # time limit reached -> go
            self.track()
            get = self.line.get()                       # ask for the next passenger in line
            if timed and env.now < deadline:
                yield get | env.timeout(deadline - env.now)   # passenger OR deadline
                if not get.triggered:                   # deadline came first
                    get.cancel()
                    continue
            else:
                yield get                               # empty jeepney: keep waiting
            pax = get.value
            self.left_line += 1
            if env.now >= self.warmup:
                self.waits.append(env.now - pax.arrival_time)
            pax.boarded.succeed()
            seats += 1
            self.log(f"passenger boards (seat {seats}/{cap})")
            yield env.timeout(self.next_board())
        return seats

    def jeepney(self, jid):
        env = self.env
        while True:
            arrive = env.now                            # joins the jeepney queue
            self.log(f"jeepney {jid} arrives at terminal")
            with self.bay.request() as req:
                yield req
                bay_enter = env.now
                self.bay_since = bay_enter
                self.log(f"jeepney {jid} enters bay")
                seats = yield from self.load()
                self.bay_busy += max(0.0, env.now - max(bay_enter, self.warmup))
                self.bay_since = None
                if env.now >= self.warmup:
                    self.seats.append(seats)
                    self.idles.append(env.now - arrive)
                self.log(f"jeepney {jid} departs with {seats} passengers")
            yield env.timeout(self.next_trip())         # round trip, then rejoin

    # ---------- results ----------
    def results(self, end):
        self.track()
        if self.bay_since is not None:                  # jeepney still in bay at the end
            self.bay_busy += end - max(self.bay_since, self.warmup)
        measured = end - self.warmup
        mean = lambda x: float(np.mean(x)) if len(x) else float("nan")
        out = {
            "avg_wait": mean(self.waits),
            "max_wait": max(self.waits) if self.waits else float("nan"),
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


def run_simulation(params, seed, log=False):
    """Run one replication and return a dict of performance measures."""
    env = simpy.Environment()
    rng = np.random.default_rng(seed)                   # seeded -> reproducible
    term = Terminal(env, params, rng, log)
    env.process(term.passenger_generator())
    for jid in range(params["fleet_size"]):
        env.process(term.jeepney(jid))
    end = params["warmup"] + params["run_length"]
    env.run(until=end)
    return term.results(end)
