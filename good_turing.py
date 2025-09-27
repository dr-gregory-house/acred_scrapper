"""
Good–Turing frequency estimator utility.

This module provides implementations of the Good–Turing smoothing for discrete events.
It supports both in-memory estimation and database-backed estimation using historical data.

Usage:
  # In-memory estimator (original)
  estimator = GoodTuringEstimator()
  estimator.update_counts({"option text A": 3, "option text B": 1})
  p_unseen = estimator.probability_of_unseen()
  p_seen_A = estimator.smoothed_probability("option text A")

  # Database-backed estimator (recommended)
  estimator = DatabaseGoodTuringEstimator(sqlite_store)
  estimator.load_from_database()
  p_unseen = estimator.probability_of_unseen()
  p_seen_A = estimator.smoothed_probability("option text A")

Notes:
  - The database-backed estimator loads all historical data for more reliable estimates
  - Supports both correct answer probabilities and total occurrence probabilities
  - Includes caching and performance optimizations for large datasets
"""

from __future__ import annotations

from typing import Dict, Tuple, Optional, Any
import time


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


class DatabaseGoodTuringEstimator:
    """Database-backed Good-Turing estimator that uses historical data from SQLiteStore.
    
    This estimator loads all historical option data from the database to provide
    more reliable probability estimates based on the complete dataset.
    """
    
    def __init__(self, sqlite_store, use_correct_answers: bool = True, cache_ttl: int = 300):
        """Initialize the database-backed estimator.
        
        Args:
            sqlite_store: SQLiteStore instance to query data from
            use_correct_answers: If True, use correct answer counts; if False, use total counts
            cache_ttl: Cache time-to-live in seconds (0 to disable caching)
        """
        self.sqlite_store = sqlite_store
        self.use_correct_answers = use_correct_answers
        self.cache_ttl = cache_ttl
        
        # Cached data
        self._cached_data: Optional[Dict[str, Any]] = None
        self._cache_timestamp: float = 0.0
        
        # Good-Turing state
        self.event_to_count: Dict[str, int] = {}
        self._total_observations: int = 0
        self._r_to_nr: Dict[int, int] = {}
        self._r_to_rstar: Dict[int, float] = {}
        
        # Additional statistics
        self._database_summary: Optional[Dict[str, Any]] = None
        self._chao1_estimate: Optional[float] = None
        
    def load_from_database(self, force_reload: bool = False) -> None:
        """Load option statistics from the database.
        
        Args:
            force_reload: If True, bypass cache and reload from database
        """
        current_time = time.time()
        
        # Check cache first
        if (not force_reload and 
            self._cached_data is not None and 
            current_time - self._cache_timestamp < self.cache_ttl):
            return
            
        print("📊 Loading historical data from database...")
        start_time = time.time()
        
        try:
            # Load option statistics
            option_stats = self.sqlite_store.get_option_statistics()
            
            # Load question hash statistics for Chao1 estimation
            qhash_stats = self.sqlite_store.get_question_hash_statistics()
            
            # Load database summary
            db_summary = self.sqlite_store.get_database_summary()
            
            # Process option data based on use_correct_answers flag
            self.event_to_count = {}
            self._total_observations = 0
            
            for text, stats in option_stats.items():
                if self.use_correct_answers:
                    count = stats['correct_count']
                else:
                    count = stats['total_count']
                
                if count > 0:
                    self.event_to_count[text] = count
                    self._total_observations += count
            
            # Compute Chao1 estimate for question diversity
            self._chao1_estimate = self._compute_chao1_estimate(qhash_stats)
            
            # Cache the data
            self._cached_data = {
                'option_stats': option_stats,
                'qhash_stats': qhash_stats,
                'db_summary': db_summary
            }
            self._cache_timestamp = current_time
            self._database_summary = db_summary
            
            # Recompute Good-Turing maps
            self._recompute_maps()
            
            load_time = time.time() - start_time
            print(f"✅ Loaded {len(self.event_to_count)} unique options from {db_summary['total_questions']} questions in {load_time:.2f}s")
            print(f"📈 Database summary: {db_summary['unique_option_texts']} unique texts, {db_summary['correct_answer_rate']:.1%} correct rate")
            
        except Exception as e:
            print(f"⚠️  Error loading from database: {e}")
            # Fallback to empty state
            self.event_to_count = {}
            self._total_observations = 0
            self._recompute_maps()
    
    def _compute_chao1_estimate(self, qhash_stats: Dict[str, int]) -> float:
        """Compute Chao1 estimate for question diversity."""
        if not qhash_stats:
            return 0.0
            
        # Chao1 = S_obs + (f1^2) / (2 * f2)
        # where f1 = singletons, f2 = doubletons, S_obs = observed species
        f1 = sum(1 for count in qhash_stats.values() if count == 1)
        f2 = sum(1 for count in qhash_stats.values() if count == 2)
        s_obs = len(qhash_stats)
        
        if f2 > 0:
            return s_obs + (f1 * f1) / (2.0 * f2)
        else:
            return float(s_obs)
    
    def get_database_summary(self) -> Optional[Dict[str, Any]]:
        """Get cached database summary statistics."""
        if self._database_summary is None:
            self.load_from_database()
        return self._database_summary
    
    def get_chao1_estimate(self) -> Optional[float]:
        """Get Chao1 estimate for question diversity."""
        if self._chao1_estimate is None:
            self.load_from_database()
        return self._chao1_estimate
    
    def probability_of_unseen(self) -> float:
        """Probability of encountering an unseen option text."""
        if self._total_observations == 0:
            return 0.0
        n1 = self._r_to_nr.get(1, 0)
        return float(n1) / float(self._total_observations)
    
    def smoothed_probability(self, event: str) -> Optional[float]:
        """Get smoothed probability for a specific option text."""
        if self._total_observations == 0:
            return None
        r = self.event_to_count.get(event)
        if r is None:
            return None
        r_star = self._r_to_rstar.get(r)
        if r_star is None:
            return float(r) / float(self._total_observations)
        return float(r_star) / float(self._total_observations)
    
    def get_confidence_interval(self, event: str, confidence: float = 0.95) -> Tuple[float, float]:
        """Get confidence interval for an option text's probability.
        
        This is a simplified implementation - in practice, you'd want more sophisticated
        confidence interval estimation for Good-Turing.
        """
        prob = self.smoothed_probability(event)
        if prob is None:
            return (0.0, 0.0)
        
        # Simple approximation: ±sqrt(prob * (1-prob) / n)
        n = self._total_observations
        if n == 0:
            return (0.0, 0.0)
            
        margin = (confidence * (prob * (1 - prob) / n) ** 0.5)
        return (max(0.0, prob - margin), min(1.0, prob + margin))
    
    def get_top_options(self, n: int = 10) -> list[Tuple[str, float, int]]:
        """Get top N options by smoothed probability.
        
        Returns list of (text, probability, raw_count) tuples.
        """
        options_with_probs = []
        for text, count in self.event_to_count.items():
            prob = self.smoothed_probability(text)
            if prob is not None:
                options_with_probs.append((text, prob, count))
        
        # Sort by probability (descending)
        options_with_probs.sort(key=lambda x: x[1], reverse=True)
        return options_with_probs[:n]
    
    def get_rare_options(self, max_count: int = 2) -> list[Tuple[str, float, int]]:
        """Get options that appear rarely (count <= max_count)."""
        rare_options = []
        for text, count in self.event_to_count.items():
            if count <= max_count:
                prob = self.smoothed_probability(text)
                if prob is not None:
                    rare_options.append((text, prob, count))
        
        # Sort by count (ascending), then by probability (descending)
        rare_options.sort(key=lambda x: (x[2], -x[1]))
        return rare_options
    
    def _recompute_maps(self) -> None:
        """Recompute Good-Turing frequency maps."""
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
                r_to_rstar[r] = float(r)
            else:
                r_to_rstar[r] = float(r + 1) * (float(nr1) / float(nr))
        self._r_to_rstar = r_to_rstar
    
    def export_state(self) -> Tuple[Dict[str, int], int, Dict[int, int]]:
        """Export current state for debugging/analysis."""
        return self.event_to_count.copy(), self._total_observations, self._r_to_nr.copy()
    
    def print_statistics(self) -> None:
        """Print concise statistics about the estimator."""
        if self._database_summary is None:
            self.load_from_database()
            
        print("📊 Database loaded: ", end="")
        if self._database_summary:
            summary = self._database_summary
            print(f"{summary['total_questions']:,} questions, {summary['unique_option_texts']:,} unique options")
        else:
            print(f"{len(self.event_to_count):,} unique options")

    def estimate_total_questions_in_pool(self) -> Dict[str, Any]:
        """Estimate total number of unique questions in the pool.

        Uses two standard richness estimators over question hashes (species):
          - Chao1 (already computed from DB hash frequencies)
          - Good–Turing coverage-based estimate: S_total ≈ S_obs / (1 - P0)

        Returns a dict with keys:
          observed, total_observations, f1, f2, p0, chao1, good_turing, combined
        """
        try:
            # Ensure DB data is loaded
            self.load_from_database()
        except Exception:
            pass

        # Pull hash frequency stats from cache or DB
        qhash_stats = None
        if self._cached_data and 'qhash_stats' in self._cached_data:
            qhash_stats = self._cached_data['qhash_stats']
        else:
            try:
                qhash_stats = self.sqlite_store.get_question_hash_statistics()
            except Exception:
                qhash_stats = {}

        if not qhash_stats:
            return {
                'observed': 0,
                'total_observations': 0,
                'f1': 0,
                'f2': 0,
                'p0': 0.0,
                'chao1': 0.0,
                'good_turing': 0.0,
                'combined': 0.0,
            }

        # Observed unique hashes and counts
        observed = len(qhash_stats)
        total_obs = sum(qhash_stats.values())
        f1 = sum(1 for c in qhash_stats.values() if c == 1)
        f2 = sum(1 for c in qhash_stats.values() if c == 2)
        p0 = (float(f1) / float(total_obs)) if total_obs > 0 else 0.0

        # Chao1 estimate (already computed for convenience)
        chao1 = self._compute_chao1_estimate(qhash_stats)

        # Good–Turing coverage-based richness estimate
        # Guard against division by zero or p0 >= 1
        if p0 >= 0.9999:
            gt_est = float(observed)
        else:
            gt_est = float(observed) / max(1e-9, (1.0 - p0))

        # Combine: use max(chao1, gt_est) as conservative upper-bound style,
        # or average as central estimate. We'll provide both via 'combined'.
        combined = max(chao1, gt_est)

        return {
            'observed': observed,
            'total_observations': total_obs,
            'f1': f1,
            'f2': f2,
            'p0': p0,
            'chao1': float(chao1),
            'good_turing': float(gt_est),
            'combined': float(combined),
        }


