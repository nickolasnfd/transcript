"""SQLite: conexão e schema idempotente (CREATE TABLE IF NOT EXISTS)."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS transcriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    duration REAL,
    language TEXT,
    model TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    error TEXT,
    text TEXT,
    segments_json TEXT
);

CREATE TABLE IF NOT EXISTS llm_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcription_id INTEGER NOT NULL REFERENCES transcriptions(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    model TEXT,
    output TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcription_id INTEGER NOT NULL REFERENCES transcriptions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Busca full-text no conteúdo dos transcripts
CREATE VIRTUAL TABLE IF NOT EXISTS transcriptions_fts USING fts5(
    text,
    filename,
    content='transcriptions',
    content_rowid='id'
);

-- Triggers para manter o índice FTS sincronizado
CREATE TRIGGER IF NOT EXISTS transcriptions_ai AFTER INSERT ON transcriptions BEGIN
    INSERT INTO transcriptions_fts(rowid, text, filename)
    VALUES (new.id, coalesce(new.text, ''), new.filename);
END;

CREATE TRIGGER IF NOT EXISTS transcriptions_ad AFTER DELETE ON transcriptions BEGIN
    INSERT INTO transcriptions_fts(transcriptions_fts, rowid, text, filename)
    VALUES ('delete', old.id, coalesce(old.text, ''), old.filename);
END;

CREATE TRIGGER IF NOT EXISTS transcriptions_au AFTER UPDATE ON transcriptions BEGIN
    INSERT INTO transcriptions_fts(transcriptions_fts, rowid, text, filename)
    VALUES ('delete', old.id, coalesce(old.text, ''), old.filename);
    INSERT INTO transcriptions_fts(rowid, text, filename)
    VALUES (new.id, coalesce(new.text, ''), new.filename);
END;
"""


def init_db(db_path: Path | None = None) -> None:
    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn(db_path: Path | None = None):
    path = db_path or settings.db_path
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
