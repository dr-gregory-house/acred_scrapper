"""
SQLite storage layer for MCQ scraper outputs.

Schema (minimal):
  - questions
      id INTEGER PRIMARY KEY AUTOINCREMENT
      set_label TEXT NULL        -- optional tag for grouping runs
      question_num TEXT NULL
      question_text TEXT NULL
      qhash TEXT NULL            -- stable content hash for duplicates
  - options
      id INTEGER PRIMARY KEY AUTOINCREMENT
      question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE
      letter TEXT NULL
      text TEXT NULL
      is_correct INTEGER NOT NULL DEFAULT 0

  - runs
      id INTEGER PRIMARY KEY AUTOINCREMENT
      label TEXT NULL
      started_at TEXT NOT NULL
      ended_at TEXT NULL
      total_questions INTEGER NOT NULL DEFAULT 0
      unique_questions INTEGER NOT NULL DEFAULT 0
      duplicate_questions INTEGER NOT NULL DEFAULT 0
      duration_seconds REAL NULL

Utility methods insert a question with options in one call and expose
basic querying helpers to accumulate frequencies for Good–Turing.
"""

from __future__ import annotations

import sqlite3
from typing import Iterable, List, Optional, Dict, Any, Tuple


class SQLiteStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._ensure_schema()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _ensure_schema(self) -> None:
        assert self._conn is not None
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_label TEXT,
                question_num TEXT,
                question_text TEXT,
                qhash TEXT
            );
            CREATE TABLE IF NOT EXISTS options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                letter TEXT,
                text TEXT,
                is_correct INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_options_question_id ON options(question_id);
            CREATE INDEX IF NOT EXISTS idx_options_text ON options(text);
            CREATE INDEX IF NOT EXISTS idx_questions_qhash ON questions(qhash);

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                total_questions INTEGER NOT NULL DEFAULT 0,
                unique_questions INTEGER NOT NULL DEFAULT 0,
                duplicate_questions INTEGER NOT NULL DEFAULT 0,
                duration_seconds REAL
            );
            """
        )
        self._conn.commit()

    def insert_question_with_options(
        self,
        set_label: Optional[str],
        question_num: Optional[str],
        question_text: Optional[str],
        options: Iterable[Dict[str, Any]],
        qhash: Optional[str] = None,
    ) -> int:
        assert self._conn is not None
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO questions (set_label, question_num, question_text, qhash) VALUES (?, ?, ?, ?)",
            (set_label, question_num, question_text, qhash),
        )
        qid = cur.lastrowid
        batch: List[Tuple[int, Optional[str], Optional[str], int]] = []
        for opt in options:
            letter = opt.get("letter")
            text = opt.get("text")
            is_correct = 1 if opt.get("is_correct") or opt.get("is_true") else 0
            batch.append((qid, letter, text, is_correct))
        if batch:
            cur.executemany(
                "INSERT INTO options (question_id, letter, text, is_correct) VALUES (?, ?, ?, ?)",
                batch,
            )
        self._conn.commit()
        return qid

    def accumulate_option_correct_counts(self) -> Dict[str, int]:
        """Return a mapping text -> count_correct where text matched as correct."""
        assert self._conn is not None
        cur = self._conn.cursor()
        cur.execute(
            "SELECT text, SUM(is_correct) FROM options WHERE text IS NOT NULL GROUP BY text"
        )
        counts: Dict[str, int] = {}
        for text, s in cur.fetchall():
            if text is None:
                continue
            counts[str(text)] = int(s or 0)
        return counts

    def get_option_statistics(self) -> Dict[str, Dict[str, int]]:
        """Return comprehensive option statistics for Good-Turing estimation.
        
        Returns: Dict[text, Dict[str, int]] where each inner dict contains:
        - 'total_count': total occurrences of this option text
        - 'correct_count': how many times it was marked as correct
        - 'incorrect_count': how many times it was marked as incorrect
        """
        assert self._conn is not None
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT 
                text,
                COUNT(*) as total_count,
                SUM(is_correct) as correct_count,
                COUNT(*) - SUM(is_correct) as incorrect_count
            FROM options 
            WHERE text IS NOT NULL 
            GROUP BY text
            ORDER BY total_count DESC
            """
        )
        stats: Dict[str, Dict[str, int]] = {}
        for text, total, correct, incorrect in cur.fetchall():
            if text is None:
                continue
            stats[str(text)] = {
                'total_count': int(total or 0),
                'correct_count': int(correct or 0),
                'incorrect_count': int(incorrect or 0)
            }
        return stats

    def get_question_hash_statistics(self) -> Dict[str, int]:
        """Return question hash frequency counts for Chao1 estimation."""
        assert self._conn is not None
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT qhash, COUNT(*) as frequency
            FROM questions 
            WHERE qhash IS NOT NULL 
            GROUP BY qhash
            ORDER BY frequency DESC
            """
        )
        counts: Dict[str, int] = {}
        for qhash, freq in cur.fetchall():
            if qhash is None:
                continue
            counts[str(qhash)] = int(freq or 0)
        return counts

    def get_database_summary(self) -> Dict[str, Any]:
        """Return comprehensive database statistics for analysis."""
        assert self._conn is not None
        cur = self._conn.cursor()
        
        # Basic counts
        cur.execute("SELECT COUNT(*) FROM questions")
        total_questions = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM options")
        total_options = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(DISTINCT text) FROM options WHERE text IS NOT NULL")
        unique_option_texts = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(DISTINCT qhash) FROM questions WHERE qhash IS NOT NULL")
        unique_question_hashes = cur.fetchone()[0]
        
        # Correct answer statistics
        cur.execute("SELECT SUM(is_correct) FROM options")
        total_correct_answers = cur.fetchone()[0] or 0
        
        # Run statistics
        cur.execute("SELECT COUNT(*) FROM runs")
        total_runs = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM runs WHERE ended_at IS NOT NULL")
        completed_runs = cur.fetchone()[0]
        
        return {
            'total_questions': total_questions,
            'total_options': total_options,
            'unique_option_texts': unique_option_texts,
            'unique_question_hashes': unique_question_hashes,
            'total_correct_answers': total_correct_answers,
            'total_runs': total_runs,
            'completed_runs': completed_runs,
            'correct_answer_rate': total_correct_answers / total_options if total_options > 0 else 0.0
        }

    def hash_exists(self, qhash: str) -> bool:
        assert self._conn is not None
        cur = self._conn.cursor()
        cur.execute("SELECT 1 FROM questions WHERE qhash = ? LIMIT 1", (qhash,))
        return cur.fetchone() is not None

    def run_start(self, label: Optional[str], started_at_iso: str) -> int:
        assert self._conn is not None
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO runs (label, started_at) VALUES (?, ?)",
            (label, started_at_iso),
        )
        self._conn.commit()
        return cur.lastrowid

    def run_finish(
        self,
        run_id: int,
        ended_at_iso: str,
        total_questions: int,
        unique_questions: int,
        duplicate_questions: int,
        duration_seconds: float,
    ) -> None:
        assert self._conn is not None
        cur = self._conn.cursor()
        cur.execute(
            """
            UPDATE runs
               SET ended_at = ?,
                   total_questions = ?,
                   unique_questions = ?,
                   duplicate_questions = ?,
                   duration_seconds = ?
             WHERE id = ?
            """,
            (
                ended_at_iso,
                total_questions,
                unique_questions,
                duplicate_questions,
                duration_seconds,
                run_id,
            ),
        )
        self._conn.commit()


