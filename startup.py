"""
Zeabur startup entry point.

Reads CORP_AUTH_STATE_JSON env var (base64-encoded corp_auth_state.json content),
writes it to disk, then launches the WARDEN orchestrator.

How to set it up on Zeabur:
  1. Go to your service → Environment Variables
  2. Add:  CORP_AUTH_STATE_JSON = <base64 output of encode_auth.py>
  3. Add all other vars from .env.example
"""
import asyncio
import base64
import json
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("startup")

AUTH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "corp_auth_state.json")


def inject_auth_state() -> bool:
    """Write corp_auth_state.json from CORP_AUTH_STATE_JSON env var."""
    raw = os.environ.get("CORP_AUTH_STATE_JSON", "").strip()
    if not raw:
        if os.path.exists(AUTH_FILE):
            log.info("corp_auth_state.json already exists on disk — using it.")
            return True
        log.error(
            "CORP_AUTH_STATE_JSON env var is not set and corp_auth_state.json "
            "does not exist. Set it on Zeabur dashboard and redeploy."
        )
        return False

    # Try base64 decode first; fall back to raw JSON string
    try:
        decoded = base64.b64decode(raw).decode("utf-8")
        json.loads(decoded)          # validate it's valid JSON
        content = decoded
        log.info("CORP_AUTH_STATE_JSON decoded from base64.")
    except Exception:
        try:
            json.loads(raw)          # maybe it was passed as raw JSON
            content = raw
            log.info("CORP_AUTH_STATE_JSON used as raw JSON.")
        except Exception as exc:
            log.error("CORP_AUTH_STATE_JSON is not valid base64 or JSON: %s", exc)
            return False

    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    log.info("corp_auth_state.json written (%d bytes).", len(content))
    return True


def check_required_env() -> bool:
    missing = []
    for var in ["TG_BOT_TOKEN", "TG_CHAT_ID"]:
        if not os.environ.get(var):
            missing.append(var)
    if missing:
        log.warning("Optional env vars not set: %s — Telegram alerts disabled.", missing)
    return True


async def run():
    from warden_orchestrator import main
    await main()


if __name__ == "__main__":
    log.info("104 AutoBot starting on Zeabur...")

    if not inject_auth_state():
        sys.exit(1)

    check_required_env()

    log.info("Launching WARDEN orchestrator...")
    asyncio.run(run())
