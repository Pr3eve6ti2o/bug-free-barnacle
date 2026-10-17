#!/usr/bin/env python3
"""Minimal SpaceHunter bot: answers /start (and any message) with a Web App
Play button pointing at the current game URL. If /start carries a numeric
payload (a ?start= deep link), it also registers the referral server-side so
attribution works even outside the mini-app start_param flow.

Config (files next to this script):
  .bot-token   the BotFather token (chmod 600)
  .game-url    the current public game URL (one line)
Proxy: uses https_proxy/HTTPS_PROXY from the environment (sandbox egress).
"""
import json
import os
import sqlite3
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN = open(os.path.join(HERE, ".bot-token")).read().strip()
GAME_URL = open(os.path.join(HERE, ".game-url")).read().strip()
API = f"https://api.telegram.org/bot{TOKEN}"
GAME_API = "http://127.0.0.1:8000/api"
DB_PATH = os.path.join(HERE, "demo.db")

proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": proxy, "https": proxy}) if proxy else urllib.request.ProxyHandler({})
)


def call(method, payload=None, timeout=45):
    req = urllib.request.Request(
        f"{API}/{method}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with opener.open(req, timeout=timeout) as r:
        return json.loads(r.read())


def register_referral(user_id, username, ref_id):
    try:
        req = urllib.request.Request(
            f"{GAME_API}/users/register_with_referral",
            data=json.dumps({"telegram_id": user_id, "username": username or "", "ref_id": ref_id}).encode(),
            # Trusted server-side call: lets this work with SPACEHUNTER_AUTH=on.
            headers={"Content-Type": "application/json", "X-Bot-Token": TOKEN},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10).read()
        print(f"referral registered: {user_id} via {ref_id}", flush=True)
    except Exception as e:  # best-effort only
        print(f"referral register failed: {e}", flush=True)


def record_bot_start(user_id):
    """Persist the /start so the 'Say hello to the bot' task can verify it."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT OR IGNORE INTO bot_starts (telegram_id) VALUES (?)", (user_id,)
        )
        conn.commit()
        conn.close()
    except Exception as e:  # best-effort only
        print(f"bot_starts record failed: {e}", flush=True)


def is_banned(user_id):
    """(banned, reason) from the game DB — suspended accounts get a notice
    instead of the Play button."""
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT banned, ban_reason FROM users WHERE telegram_id=?", (user_id,)
        ).fetchone()
        conn.close()
        if row and row[0]:
            return True, (row[1] or "")
    except Exception:
        pass
    return False, ""


def play_markup():
    return {"inline_keyboard": [[{"text": "🚀 Play SpaceHunter", "web_app": {"url": GAME_URL}}]]}


def handle(msg):
    chat_id = msg["chat"]["id"]
    user = msg.get("from", {})
    text = (msg.get("text") or "").strip()
    if text.startswith("/start"):
        if user.get("id"):
            record_bot_start(user["id"])
            banned, reason = is_banned(user["id"])
            if banned:
                body = ("🚫 <b>Account suspended</b>\n\n"
                        "Your game account has been suspended by the team."
                        + (f"\nReason: {reason}" if reason else "")
                        + "\n\nIf you think this is a mistake, contact support.")
                try:
                    call("sendMessage", {"chat_id": chat_id, "text": body, "parse_mode": "HTML"})
                except Exception as e:
                    print(f"sendMessage failed: {e}", flush=True)
                return
        parts = text.split(maxsplit=1)
        if len(parts) == 2 and parts[1].isdigit() and int(parts[1]) != user.get("id"):
            register_referral(user.get("id"), user.get("username"), int(parts[1]))
        body = (
            "🚀 <b>SpaceHunter</b>\n\n"
            "Tap the ship to mine CSM, claim daily bonuses, spin the arcade "
            "wheel and grow your crew — every friend who starts mining earns "
            "you a share of their yield.\n\nTap <b>Play</b> to launch the game:"
        )
    else:
        body = "Tap <b>Play</b> to jump back into SpaceHunter:"
    try:
        call("sendMessage", {
            "chat_id": chat_id,
            "text": body,
            "parse_mode": "HTML",
            "reply_markup": play_markup(),
        })
    except Exception as e:
        print(f"sendMessage failed: {e}", flush=True)


def maybe_daily_digest():
    """Once a day at the configured UTC hour, post the day's REAL payout
    totals to the proofs channel (only when at least one payout happened)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        settings = dict(conn.execute(
            "SELECT key, value FROM admin_settings WHERE key IN "
            "('digest_enabled','digest_hour_utc','proofs_channel_id','digest_last_date')"
        ).fetchall())
        if settings.get("digest_enabled") != "1":
            conn.close()
            return
        channel = settings.get("proofs_channel_id", "")
        hour = int(settings.get("digest_hour_utc", "12") or 12)
        now = time.gmtime()
        today = time.strftime("%Y-%m-%d", now)
        if now.tm_hour != hour or settings.get("digest_last_date") == today:
            conn.close()
            return
        count, total = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM withdrawal_requests "
            "WHERE status='paid' AND date(paid_at) = date('now')"
        ).fetchone()
        conn.execute(
            "INSERT INTO admin_settings (key, value) VALUES ('digest_last_date', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (today,))
        conn.commit()
        conn.close()
        if channel and count:
            text = (f"📊 <b>Daily payout summary</b>\n\n"
                    f"Today the crew cashed out <b>{int(total):,} CSM</b> "
                    f"across <b>{int(count)}</b> payout{'s' if count != 1 else ''}. 💸")
            call("sendMessage", {"chat_id": channel, "text": text, "parse_mode": "HTML",
                                 "disable_web_page_preview": True})
            print(f"daily digest posted: {count} payouts, {total} CSM", flush=True)
    except Exception as e:
        print(f"digest check failed: {e}", flush=True)


def main():
    print(f"bot polling; game url: {GAME_URL}", flush=True)
    offset = None
    while True:
        maybe_daily_digest()
        try:
            res = call("getUpdates", {"offset": offset, "timeout": 30,
                                      "allowed_updates": ["message"]}, timeout=40)
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message")
                if msg:
                    handle(msg)
        except urllib.error.HTTPError as e:
            print(f"getUpdates HTTP {e.code}; backing off", flush=True)
            time.sleep(5)
        except Exception as e:
            print(f"getUpdates error: {e}; backing off", flush=True)
            time.sleep(3)


if __name__ == "__main__":
    main()
