"""SQLite history layer, compatible with App.py's timestamp schema."""
import sqlite3
from datetime import datetime
from config import DB_PATH


def get_connection():
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


def _columns(conn):
    return {row[1] for row in conn.execute("PRAGMA table_info(analysis_history)").fetchall()}


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                last_close REAL,
                score INTEGER,
                decision TEXT,
                buy_zone TEXT,
                target_price TEXT,
                stop_loss TEXT,
                summary TEXT
            )
        """)
        conn.commit()


def save_analysis(symbol, last_close, score, decision, buy_zone, target_price, stop_loss, summary):
    init_db()
    with get_connection() as conn:
        cols = _columns(conn)
        time_col = "timestamp" if "timestamp" in cols else "analyzed_at"
        sql = f"""
            INSERT INTO analysis_history
            (symbol, {time_col}, last_close, score, decision, buy_zone, target_price, stop_loss, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        conn.execute(sql, (
            str(symbol).upper(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            float(last_close), int(score), str(decision), str(buy_zone),
            str(target_price), str(stop_loss), str(summary)
        ))
        conn.commit()


def get_recent_history(symbol=None, limit=10):
    init_db()
    with get_connection() as conn:
        cols = _columns(conn)
        time_col = "timestamp" if "timestamp" in cols else "analyzed_at"
        base = f"SELECT symbol, {time_col}, last_close, decision, buy_zone, target_price, stop_loss, summary FROM analysis_history"
        if symbol:
            rows = conn.execute(
                base + " WHERE symbol = ? ORDER BY id DESC LIMIT ?",
                (str(symbol).upper(), int(limit))
            ).fetchall()
        else:
            rows = conn.execute(base + " ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        return rows
