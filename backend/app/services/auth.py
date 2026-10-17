"""Telegram WebApp initData verification (the real authentication layer).

Every API identity in this app is a telegram_id supplied by the client.
That is only safe if the server verifies the Telegram-signed initData that
accompanies the request: Telegram signs the launch parameters with the bot
token, so a valid HMAC proves the request really comes from that Telegram
user inside the bot's mini app.

Enforcement is env-gated: SPACEHUNTER_AUTH=on turns on the middleware in
app/main.py. The browser-based demo runs with it off because the demo's
mock Telegram environment cannot produce a genuine signature — for any
real deployment behind the bot it MUST be on.
"""
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qsl

# Load backend/.env explicitly so SPACEHUNTER_AUTH applies under every
# launch path (not only when the shell exported it).
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except Exception:
    pass

_MAX_AGE_SECONDS = 24 * 3600


def auth_required() -> bool:
    return os.environ.get("SPACEHUNTER_AUTH", "off").lower() == "on"


def _bot_token() -> str | None:
    token = os.environ.get("BOT_TOKEN")
    if token:
        return token.strip()
    # Demo convenience: the bot token file stored next to the demo root.
    try:
        p = Path(__file__).resolve().parents[3] / ".bot-token"
        if p.exists():
            return p.read_text().strip()
    except Exception:
        pass
    return None


def verify_init_data(init_data: str, max_age: int = _MAX_AGE_SECONDS) -> int | None:
    """Return the verified Telegram user id, or None if the signature is
    missing/invalid/stale. Implements Telegram's documented algorithm:
    secret = HMAC_SHA256(key='WebAppData', msg=bot_token);
    hash   = HMAC_SHA256(key=secret, msg=data_check_string)."""
    token = _bot_token()
    if not token or not init_data:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None
    received = pairs.pop("hash", None)
    if not received:
        return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received):
        return None
    try:
        auth_date = int(pairs.get("auth_date", "0"))
        age = time.time() - auth_date
        if auth_date <= 0 or age > max_age or age < -300:
            return None
        user = json.loads(pairs.get("user", "{}"))
        return int(user["id"])
    except Exception:
        return None
