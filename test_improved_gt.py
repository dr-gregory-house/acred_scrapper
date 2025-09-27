#!/usr/bin/env python3
"""
Test script to demonstrate the improved Good-Turing implementation.
This script shows how the database-backed estimator provides more reliable estimates.
"""

import os
import sys
from sqlite_store import SQLiteStore
from good_turing import GoodTuringEstimator, DatabaseGoodTuringEstimator

def test_improved_good_turing():
    """Test the improved Good-Turing implementation."""
    print("🧪 Testing Improved Good-Turing Implementation")
    print("=" * 60)
    
    # Check if database exists
    db_path = "mcq.db"
    if not os.path.exists(db_path):
        print(f"❌ Database {db_path} not found. Please run the reconnaissance script first.")
        return
    
    try:
        # Initialize database store
        store = SQLiteStore(db_path)
        store.connect()
        
        # Get database summary
        summary = store.get_database_summary()
        print(f"\n📊 Database Summary:")
        print(f"  Total questions: {summary['total_questions']:,}")
        print(f"  Total options: {summary['total_options']:,}")
        print(f"  Unique option texts: {summary['unique_option_texts']:,}")
        print(f"  Correct answer rate: {summary['correct_answer_rate']:.1%}")
        
        if summary['total_questions'] == 0:
            print("❌ No data in database. Please run the reconnaissance script first.")
            return
        
        # Test original estimator (session-only)
        print(f"\n🔬 Testing Original GoodTuringEstimator (Session-only):")
        original_estimator = GoodTuringEstimator()
        
        # Simulate some session data
        session_data = {
            "Option A": 2,
            "Option B": 1,
            "Option C": 3
        }
        original_estimator.update_counts(session_data)
        
        print(f"  Session observations: {original_estimator._total_observations}")
        print(f"  Session unique events: {len(original_estimator.event_to_count)}")
        print(f"  P(unseen): {original_estimator.probability_of_unseen():.4f}")
        
        # Test database-backed estimator
        print(f"\n🔬 Testing DatabaseGoodTuringEstimator (Historical data):")
        db_estimator = DatabaseGoodTuringEstimator(store, use_correct_answers=True, cache_ttl=0)
        db_estimator.load_from_database()
        
        # Print comprehensive statistics
        db_estimator.print_statistics()

        # Estimate total pool size
        print(f"\n📦 Estimating total question pool size:")
        pool = db_estimator.estimate_total_questions_in_pool()
        print(f"  Observed unique (in DB): {pool['observed']}")
        print(f"  Total observations (hash draws): {pool['total_observations']}")
        print(f"  Singletons f1: {pool['f1']}, Doubletons f2: {pool['f2']}")
        print(f"  Coverage P0≈ {pool['p0']:.4f}")
        print(f"  Chao1≈ {pool['chao1']:.1f}")
        print(f"  Good–Turing≈ {pool['good_turing']:.1f}")
        print(f"  Combined (max)≈ {pool['combined']:.1f}")
        
        # Compare estimates for some options
        print(f"\n📈 Comparison of Estimates:")
        print(f"{'Option Text':<30} {'Session P':<10} {'Database P':<10} {'Database CI':<20}")
        print("-" * 70)
        
        # Get some sample options from database
        option_stats = store.get_option_statistics()
        sample_options = list(option_stats.keys())[:5]
        
        for option_text in sample_options:
            session_p = original_estimator.smoothed_probability(option_text)
            db_p = db_estimator.smoothed_probability(option_text)
            ci_low, ci_high = db_estimator.get_confidence_interval(option_text)
            
            session_str = f"{session_p:.4f}" if session_p is not None else "N/A"
            db_str = f"{db_p:.4f}" if db_p is not None else "N/A"
            ci_str = f"[{ci_low:.3f}, {ci_high:.3f}]" if db_p is not None else "N/A"
            
            print(f"{option_text[:29]:<30} {session_str:<10} {db_str:<10} {ci_str:<20}")
        
        # Show top options from database
        print(f"\n🏆 Top 5 Most Probable Options (from database):")
        top_options = db_estimator.get_top_options(5)
        for i, (text, prob, count) in enumerate(top_options, 1):
            print(f"  {i}. '{text[:60]}{'...' if len(text) > 60 else ''}'")
            print(f"     Probability: {prob:.4f}, Count: {count}")
        
        # Show rare options
        print(f"\n🔍 Rare Options (count ≤ 2):")
        rare_options = db_estimator.get_rare_options(2)
        for i, (text, prob, count) in enumerate(rare_options[:5], 1):
            print(f"  {i}. '{text[:60]}{'...' if len(text) > 60 else ''}'")
            print(f"     Probability: {prob:.4f}, Count: {count}")
        
        # Test different modes
        print(f"\n🔄 Testing Different Modes:")
        
        # Correct answers only
        correct_estimator = DatabaseGoodTuringEstimator(store, use_correct_answers=True, cache_ttl=0)
        correct_estimator.load_from_database()
        
        # Total counts
        total_estimator = DatabaseGoodTuringEstimator(store, use_correct_answers=False, cache_ttl=0)
        total_estimator.load_from_database()
        
        print(f"  Correct answers mode: {correct_estimator._total_observations:,} observations")
        print(f"  Total counts mode: {total_estimator._total_observations:,} observations")
        print(f"  Correct P(unseen): {correct_estimator.probability_of_unseen():.4f}")
        print(f"  Total P(unseen): {total_estimator.probability_of_unseen():.4f}")
        
        store.close()
        print(f"\n✅ Test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_improved_good_turing()
