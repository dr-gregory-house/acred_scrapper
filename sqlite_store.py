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


