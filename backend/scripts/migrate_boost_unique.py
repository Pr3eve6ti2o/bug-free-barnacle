"""One-off migration: user_boosts uniqueness.

user_boosts has a surrogate PK and no UNIQUE(user_id, boost_id), so two
concurrent first-time upgrades of the same boost could insert duplicate
rows and charge twice for one level (found by the Opus redo audit, S11 —
the guarded level UPDATE only helps once a row exists).

Idempotent: normalises every row's level to the pair maximum, deletes
duplicates keeping one row per (user_id, boost_id), then adds the unique
index. Safe to run repeatedly.
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "demo.db"


def main() -> None:
    conn = sqlite3.connect(DB)
    try:
        # Every duplicate row takes the pair's max level first, so deleting
        # all but one row per pair can never lose a purchased level.
        conn.execute(
            "UPDATE user_boosts SET level = ("
            "  SELECT MAX(level) FROM user_boosts x"
            "  WHERE x.user_id = user_boosts.user_id AND x.boost_id = user_boosts.boost_id)"
        )
        before = conn.execute("SELECT COUNT(*) FROM user_boosts").fetchone()[0]
        conn.execute(
            "DELETE FROM user_boosts WHERE id NOT IN ("
            "  SELECT MAX(id) FROM user_boosts GROUP BY user_id, boost_id)"
        )
        after = conn.execute("SELECT COUNT(*) FROM user_boosts").fetchone()[0]
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_user_boost "
            "ON user_boosts (user_id, boost_id)"
        )
        conn.commit()
        print(f"user_boosts: {before} -> {after} rows; ux_user_boost present")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
