"""
WARDEN Checker Module -- 104 Notification Monitor
Monitors the corporate portal for new unread notifications (replies from candidates).

Architecture Note:
  The ASM (Advanced Search Module) is not activated on this account.
  Proactive talent-pool search requires ASM activation (contact 104 sales).
  This module instead monitors incoming notifications via the internal XHR API:
    GET https://pro.104.com.tw/commons/api/countUnreadNotification
  The API returns {"code":200,"data":{"count":<N>}} when called from an
  authenticated page context (requires browser + cookies, not plain requests).
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from playwright.async_api import Page

logger = logging.getLogger(__name__)

HRSYSTEM_URL    = "https://pro.104.com.tw/hrsystem"
NOTIFY_API      = "https://pro.104.com.tw/commons/api/countUnreadNotification"
MSG_CENTER_URL  = "https://pro.104.com.tw/hrsystem/message"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notification_state (
    id              INTEGER PRIMARY KEY,
    checked_at      TEXT NOT NULL,
    unread_count    INTEGER NOT NULL,
    delta           INTEGER NOT NULL DEFAULT 0
);
"""


@dataclass
class NotificationResult:
    unread_count:  int
    prev_count:    int
    delta:         int            # positive = new activity
    checked_at:    str
    has_new_activity: bool


async def fetch_unread_count(page: Page) -> int:
    """
    Call the notification API via in-page XHR (requires authenticated page context).
    Returns the unread count, or -1 on failure.
    """
    try:
        result = await page.evaluate("""async () => {
            const r = await fetch('https://pro.104.com.tw/commons/api/countUnreadNotification', {
                credentials: 'include',
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            if (!r.ok) return {code: r.status, data: {count: -1}};
            return await r.json();
        }""")
        if result and result.get("code") == 200:
            count = result.get("data", {}).get("count", -1)
            logger.info("WARDEN -> unread count: %d", count)
            return count
        else:
            logger.warning("WARDEN -> unexpected response: %s", result)
            return -1
    except Exception as exc:
        logger.error("WARDEN -> fetch_unread_count error: %s", exc)
        return -1


async def check_notifications(page: Page) -> NotificationResult:
    """
    Navigate to hrsystem and check the unread notification count.
    Returns a NotificationResult with delta vs. last stored count.
    """
    logger.info("WARDEN -> navigating to %s", HRSYSTEM_URL)
    try:
        await page.goto(HRSYSTEM_URL, wait_until="domcontentloaded", timeout=20000)
        import asyncio
        await asyncio.sleep(3)
    except Exception as exc:
        logger.error("WARDEN -> navigation error: %s", exc)
        return NotificationResult(-1, -1, 0, datetime.now().isoformat(), False)

    count = await fetch_unread_count(page)
    now   = datetime.now().isoformat()

    return NotificationResult(
        unread_count=count,
        prev_count=-1,       # filled in by load_and_compare()
        delta=0,
        checked_at=now,
        has_new_activity=False,
    )


# ─── SQLite helpers ───────────────────────────────────────────────────────────

def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def load_last_count(db_path: str) -> int:
    """Return the most recent stored unread count, or 0 if none."""
    try:
        conn = _get_conn(db_path)
        row  = conn.execute(
            "SELECT unread_count FROM notification_state ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return row[0] if row else 0
    except sqlite3.Error as exc:
        logger.error("DB load error: %s", exc)
        return 0


def save_count(db_path: str, count: int, delta: int) -> bool:
    """Persist a notification check result."""
    try:
        conn = _get_conn(db_path)
        conn.execute(
            "INSERT INTO notification_state (checked_at, unread_count, delta) VALUES (?,?,?)",
            (datetime.now().isoformat(), count, delta),
        )
        conn.commit()
        conn.close()
        logger.info("WARDEN -> saved count=%d delta=%d", count, delta)
        return True
    except sqlite3.Error as exc:
        logger.error("DB save error: %s", exc)
        return False


async def check_and_compare(page: Page, db_path: str) -> NotificationResult:
    """
    Full WARDEN workflow:
      1. Load hrsystem, fetch unread count via XHR
      2. Compare with last stored count
      3. Persist new count
      4. Return result with delta and has_new_activity flag
    """
    result = await check_notifications(page)
    if result.unread_count < 0:
        return result

    prev = load_last_count(db_path)
    delta = result.unread_count - prev
    result.prev_count        = prev
    result.delta             = delta
    result.has_new_activity  = delta > 0

    save_count(db_path, result.unread_count, delta)
    logger.info("WARDEN -> prev=%d current=%d delta=%d new_activity=%s",
                prev, result.unread_count, delta, result.has_new_activity)
    return result
