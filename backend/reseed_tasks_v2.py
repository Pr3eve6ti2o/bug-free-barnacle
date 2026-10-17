#!/usr/bin/env python3
"""One-off migration + reseed for the farming redesign (run with the server stopped):
- game_states.task_boost_pct, tasks.reward_type / multiplier_pct / link_url columns
- bot_starts table (drives the 'open the bot' task detection)
- replaces the old tap-era task set with the starter set:
  token rewards and mining-multiplier rewards, all server-detectable.
"""
import sqlite3
import os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "demo.db")
c = sqlite3.connect(DB)


def add_column(table, column, ddl):
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})")]
    if column not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
        print(f"added {table}.{column}")


add_column("game_states", "task_boost_pct", "task_boost_pct FLOAT DEFAULT 0")
add_column("tasks", "reward_type", "reward_type TEXT DEFAULT 'token'")
add_column("tasks", "multiplier_pct", "multiplier_pct FLOAT DEFAULT 0")
add_column("tasks", "link_url", "link_url TEXT")

c.execute(
    """CREATE TABLE IF NOT EXISTS bot_starts (
           telegram_id INTEGER PRIMARY KEY,
           started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
       )"""
)

BOT = "https://t.me/FARMGradientbot"
TASKS = [
    # title, description, type, condition_type, condition_value, reward, reward_type, multiplier_pct, link_url
    ("First launch", "Start your first mining session", "permanent", "mining_sessions", 1, 250, "token", 0, None),
    ("Full cycle", "Claim a completed mining session", "permanent", "mining_claims", 1, 0, "multiplier", 5, None),
    ("Say hello to the bot", "Open the game bot and press /start", "permanent", "bot_started", 1, 150, "token", 0, BOT),
    ("First friend", "Invite 1 friend to the game", "permanent", "referrals", 1, 500, "token", 0, None),
    ("Crew of five", "Invite 5 friends to the game", "permanent", "referrals", 5, 0, "multiplier", 10, None),
    ("Steady miner", "Claim 3 mining sessions", "permanent", "mining_claims", 3, 750, "token", 0, None),
    ("Four figures", "Hold 1,000 CSM in your balance", "permanent", "balance", 1000, 0, "multiplier", 10, None),
    ("Levelling up", "Reach level 3", "permanent", "level", 3, 400, "token", 0, None),
    ("Wallet ready", "Connect a TON wallet", "permanent", "wallet_connected", 1, 0, "multiplier", 5, None),
]

c.execute("DELETE FROM user_tasks")
c.execute("DELETE FROM tasks")
c.executemany(
    """INSERT INTO tasks (title, description, type, condition_type, condition_value,
                          reward, reward_type, multiplier_pct, link_url)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    TASKS,
)
c.commit()
print("tasks reseeded:", c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])
print("bot_starts rows:", c.execute("SELECT COUNT(*) FROM bot_starts").fetchone()[0])
c.close()
