"""
Good–Turing frequency estimator utility.

This module provides a small, dependency-free implementation of the
Good–Turing smoothing for discrete events. It is designed to be fed
with observed event counts (e.g., how many times a specific option text
was observed as correct), and then returns smoothed probabilities for
seen and unseen events.

Usage:
  estimator = GoodTuringEstimator()
  estimator.update_counts({"option text A": 3, "option text B": 1})
  p_unseen = estimator.probability_of_unseen()
  p_seen_A = estimator.smoothed_probability("option text A")

Notes:
  - This is a compact implementation intended for small-to-medium sized
    vocabularies; it recomputes the r->r* map upon updates.
  - If no counts are provided, the estimator returns None for seen
    events and 0.0 for unseen probability.
"""

from __future__ import annotations

from typing import Dict, Tuple


class GoodTuringEstimator:
    def __init__(self) -> None:
        self.event_to_count: Dict[str, int] = {}
        self._total_observations: int = 0
        self._r_to_nr: Dict[int, int] = {}
        self._r_to_rstar: Dict[int, float] = {}

    def update_counts(self, counts: Dict[str, int]) -> None:
        for event, cnt in counts.items():
            if cnt <= 0:
                continue
            prev = self.event_to_count.get(event, 0)
            self.event_to_count[event] = prev + cnt
            self._total_observations += cnt
        self._recompute_maps()

    def increment(self, event: str, by: int = 1) -> None:
        if by <= 0:
            return
        prev = self.event_to_count.get(event, 0)
        self.event_to_count[event] = prev + by
        self._total_observations += by
        self._recompute_maps()

    def probability_of_unseen(self) -> float:
        # P0 = N1 / N, where N1 is number of singleton types, N is total tokens
        if self._total_observations == 0:
            return 0.0
        n1 = self._r_to_nr.get(1, 0)
        return float(n1) / float(self._total_observations)

    def smoothed_probability(self, event: str) -> float | None:
        if self._total_observations == 0:
            return None
        r = self.event_to_count.get(event)
        if r is None:
            # Unseen event; caller can use probability_of_unseen() / Z
            return None
        r_star = self._r_to_rstar.get(r)
        if r_star is None:
            # Fallback to MLE if something went wrong in mapping
            return float(r) / float(self._total_observations)
        return float(r_star) / float(self._total_observations)

    def _recompute_maps(self) -> None:
        r_to_nr: Dict[int, int] = {}
        for r in self.event_to_count.values():
            r_to_nr[r] = r_to_nr.get(r, 0) + 1
        self._r_to_nr = r_to_nr

        # Compute r* using the simple Good–Turing formula:
        # r* = (r + 1) * (N_{r+1} / N_r)
        r_to_rstar: Dict[int, float] = {}
        for r, nr in r_to_nr.items():
            nr1 = r_to_nr.get(r + 1)
            if nr1 is None or nr == 0:
                # If no N_{r+1}, fallback to r
                r_to_rstar[r] = float(r)
            else:
                r_to_rstar[r] = float(r + 1) * (float(nr1) / float(nr))
        self._r_to_rstar = r_to_rstar

    def export_state(self) -> Tuple[Dict[str, int], int, Dict[int, int]]:
        return self.event_to_count.copy(), self._total_observations, self._r_to_nr.copy()


