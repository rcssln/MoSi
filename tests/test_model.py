"""Verification tests. Run from the project folder:  python -m unittest discover tests"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from terminal_model import run_simulation


def seq(values):
    """Sampler that returns the listed values in order, then repeats the last one."""
    it = iter(values)
    last = [values[-1]]
    def f():
        last[0] = next(it, last[0])
        return last[0]
    return f


def params(**kw):
    p = {**config.BASE_PARAMS, "rule": "baseline", "time_limit": None,
         "fleet_size": 1, "mean_interarrival": 1.0, "warmup": 0, "run_length": 100}
    p.update(kw)
    return p


class TestModel(unittest.TestCase):
    def test_hand_case_baseline(self):
        # C=2, N=1. A passenger every 1 min (first at t=1), boarding 0.5 min, trip 10 min.
        # By hand: bay entered t=0; P1 at 1, P2 at 2 -> full, depart 2.5 (idle 2.5).
        # Back at 12.5: P3 (arrived 3) waits 9.5, P4 (arrived 4) waits 9.0 -> depart 13.5 (idle 1.0).
        # 20 arrivals by t=20.5, 4 boarded, 16 waiting. Bay busy 2.5 + 1.0 = 3.5.
        p = params(capacity=2, run_length=20.5, arrival_sampler=lambda: 1.0,
                   board_sampler=lambda: 0.5, trip_sampler=lambda: 10.0)
        r = run_simulation(p, seed=1)
        self.assertEqual(r["departures"], 2)
        self.assertEqual((r["arrived"], r["boarded"], r["still_waiting"]), (20, 4, 16))
        self.assertAlmostEqual(r["avg_wait"], (0 + 0 + 9.5 + 9.0) / 4)
        self.assertAlmostEqual(r["max_wait"], 9.5)
        self.assertAlmostEqual(r["avg_seats"], 2.0)
        self.assertAlmostEqual(r["avg_idle"], (2.5 + 1.0) / 2)
        self.assertAlmostEqual(r["bay_util"], 3.5 / 20.5)

    def test_hand_case_timed(self):
        # C=4, T=3, arrivals at 1.5, 2.5, 3.5... instant boarding.
        # Two on board at t=3 -> departs at exactly t=3 with 2 passengers.
        p = params(capacity=4, rule="timed", time_limit=3, run_length=4,
                   arrival_sampler=seq([1.5, 1.0]), board_sampler=lambda: 0.0,
                   trip_sampler=lambda: 50.0)
        r = run_simulation(p, seed=1, log=True)
        self.assertEqual(r["departures"], 1)
        self.assertEqual(r["avg_seats"], 2)
        self.assertAlmostEqual(r["avg_idle"], 3.0)
        self.assertTrue(any("3.00" in l and "departs with 2" in l for l in r["log"]))

    def test_timed_waits_for_first_passenger(self):
        # T=3 elapses with nobody on board; first passenger arrives at t=5 -> depart at 5 with 1.
        p = params(capacity=4, rule="timed", time_limit=3, run_length=6,
                   arrival_sampler=seq([5.0, 100.0]), board_sampler=lambda: 0.0,
                   trip_sampler=lambda: 50.0)
        r = run_simulation(p, seed=1)
        self.assertEqual(r["departures"], 1)
        self.assertEqual(r["avg_seats"], 1)
        self.assertAlmostEqual(r["avg_idle"], 5.0)

    def test_conservation_random_runs(self):
        for rule, t in (("baseline", None), ("timed", 5)):
            for seed in range(5):
                p = params(rule=rule, time_limit=t, fleet_size=3, mean_interarrival=0.5,
                           warmup=30, run_length=200)
                r = run_simulation(p, seed)
                self.assertEqual(r["arrived"], r["boarded"] + r["still_waiting"])

    def test_no_arrivals(self):
        p = params(arrival_sampler=lambda: 1e9)
        r = run_simulation(p, seed=1)
        self.assertEqual((r["arrived"], r["boarded"], r["departures"]), (0, 0, 0))
        self.assertEqual(r["served_per_hour"], 0)
        self.assertEqual(r["avg_waiting"], 0)
        self.assertTrue(math.isnan(r["avg_wait"]))

    def test_very_high_arrivals(self):
        # Huge demand and many jeepneys: every jeepney leaves full and the bay is nearly always busy.
        p = params(capacity=4, fleet_size=30, mean_interarrival=0.001, trip_sampler=lambda: 5.0,
                   warmup=10, run_length=100)
        r = run_simulation(p, seed=1)
        self.assertEqual(r["avg_seats"], 4)
        self.assertGreater(r["bay_util"], 0.95)
        self.assertGreater(r["avg_waiting"], 100)
        self.assertEqual(r["arrived"], r["boarded"] + r["still_waiting"])

    def test_reproducible(self):
        p = {**config.BASE_PARAMS, **config.SCENARIOS[1]}
        self.assertEqual(run_simulation(p, 7), run_simulation(p, 7))


if __name__ == "__main__":
    unittest.main()
