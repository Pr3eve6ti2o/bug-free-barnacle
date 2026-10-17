"""Admin-panel migration (2026-10-17): ban fields, admin mining boost,
withdrawal review fields. Idempotent — safe to re-run."""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "demo.db"


def add_column(cur, table: str, column: str, ddl: str) -> None:
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        print(f"added {table}.{column}")


def main() -> None:
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    add_column(cur, "users", "banned", "BOOLEAN NOT NULL DEFAULT 0")
    add_column(cur, "users", "ban_reason", "VARCHAR")
    add_column(cur, "game_states", "admin_boost_pct", "FLOAT DEFAULT 0")
    add_column(cur, "withdrawal_requests", "reviewed_by", "BIGINT")
    add_column(cur, "withdrawal_requests", "reviewed_at", "DATETIME")
    add_column(cur, "withdrawal_requests", "tx_hash", "VARCHAR")
    add_column(cur, "withdrawal_requests", "paid_at", "DATETIME")
    add_column(cur, "tasks", "is_active", "BOOLEAN NOT NULL DEFAULT 1")
    conn.commit()
    conn.close()
    print("admin panel migration done")


if __name__ == "__main__":
    main()
