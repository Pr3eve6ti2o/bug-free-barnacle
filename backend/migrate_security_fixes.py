#!/usr/bin/env python3
"""Security-fix migration (run with the server stopped):
- users.lifetime_mined column, backfilled from lifetime_earned so existing
  players keep their qualification standing; new accounts start at 0 and can
  only raise it by actually mining (escrow/bonus credits no longer count).
- UNIQUE index on user_tasks(user_id, task_id) after dedupe — stops the
  concurrent check_progress duplicate-row double-claim.
- Partial UNIQUE index on mining_sessions(user_id) WHERE claimed = 0 — makes
  'one unclaimed session per user' a database guarantee, not a race.
"""
import sqlite3
import os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "demo.db")
c = sqlite3.connect(DB)

cols = [r[1] for r in c.execute("PRAGMA table_info(users)")]
if "lifetime_mined" not in cols:
    c.execute("ALTER TABLE users ADD COLUMN lifetime_mined INTEGER DEFAULT 0 NOT NULL")
    c.execute("UPDATE users SET lifetime_mined = lifetime_earned")
    print("added users.lifetime_mined + backfilled")

dupes = c.execute(
    """SELECT user_id, task_id, COUNT(*) n FROM user_tasks
       GROUP BY user_id, task_id HAVING n > 1"""
).fetchall()
for user_id, task_id, _n in dupes:
    rows = c.execute(
        "SELECT id, is_claimed, is_completed, progress FROM user_tasks WHERE user_id=? AND task_id=? ORDER BY id",
        (user_id, task_id),
    ).fetchall()
    keep = rows[0][0]
    claimed = any(r[1] for r in rows)
    completed = any(r[2] for r in rows)
    progress = max(r[3] or 0 for r in rows)
    c.execute(
        "UPDATE user_tasks SET is_claimed=?, is_completed=?, progress=? WHERE id=?",
        (claimed, completed, progress, keep),
    )
    c.execute(
        "DELETE FROM user_tasks WHERE user_id=? AND task_id=? AND id<>?",
        (user_id, task_id, keep),
    )
    print(f"deduped user_tasks user={user_id} task={task_id}: kept {keep}")
c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_user_task ON user_tasks(user_id, task_id)")
print("ux_user_task ready")

# If duplicate unclaimed sessions already exist for a user, keep the newest
# claimable one and mark the older ones claimed (amount 0 history is not
# tracked on the row; they were never paid).
multi = c.execute(
    """SELECT user_id, COUNT(*) n FROM mining_sessions WHERE claimed = 0
       GROUP BY user_id HAVING n > 1"""
).fetchall()
for user_id, _n in multi:
    rows = c.execute(
        "SELECT id FROM mining_sessions WHERE user_id=? AND claimed=0 ORDER BY id DESC",
        (user_id,),
    ).fetchall()
    for (sid,) in rows[1:]:
        c.execute("UPDATE mining_sessions SET claimed=1 WHERE id=?", (sid,))
    print(f"user {user_id}: collapsed duplicate active sessions")
c.execute(
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_mining_unclaimed ON mining_sessions(user_id) WHERE claimed = 0"
)
print("ux_mining_unclaimed ready")

c.commit()
c.close()
print("migration done")
