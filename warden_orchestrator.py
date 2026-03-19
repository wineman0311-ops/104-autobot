"""
WARDEN Orchestrator -- Main Scheduler & Job Coordinator
Daily cron that ties PHANTOM / WARDEN / HERALD together.

Current capability (v2):
  - PHANTOM  : Cookie-based login via corp_auth_state.json
  - WARDEN   : Monitors unread-notification count delta via XHR API
  - HERALD   : Sends Telegram alerts when new activity is detected
  - SCOUT    : Stub (requires ASM activation -- contact 104 sales)
  - COURIER  : Stub (requires ASM activation -- contact 104 sales)
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()


def setup_logging(log_dir: str = "logs") -> None:
    Path(log_dir).mkdir(exist_ok=True)
    log_file = Path(log_dir) / f"warden_{datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"),
                  logging.StreamHandler()],
    )


logger = logging.getLogger("WARDEN")


# -- Config -------------------------------------------------------------------

class Config:
    ACCOUNT_EMAIL   = os.getenv("ACCOUNT_EMAIL",   "")
    ACCOUNT_PW      = os.getenv("ACCOUNT_PASSWORD","")
    TG_BOT_TOKEN    = os.getenv("TG_BOT_TOKEN",    "")
    TG_CHAT_ID      = os.getenv("TG_CHAT_ID",      "")
    SCHEDULE_TIME   = os.getenv("SCHEDULE_TIME",      "09:00")
    SCHEDULE_TZ     = os.getenv("SCHEDULE_TIMEZONE",  "Asia/Taipei")
    DB_PATH         = os.getenv("DB_PATH",             "warden.db")
    HEADLESS        = os.getenv("HEADLESS", "true").lower() == "true"
    MSG_CENTER_URL  = "https://pro.104.com.tw/hrsystem/message"

    @classmethod
    def validate(cls) -> bool:
        if not cls.TG_BOT_TOKEN or not cls.TG_CHAT_ID:
            logger.warning("Telegram not configured -- notifications disabled")
        return True  # non-fatal; pipeline still runs


# -- Module imports -----------------------------------------------------------

from phantom_browser import get_authenticated_page, close_browser
from warden_checker  import check_and_compare
from herald_notifier import TelegramNotifier


# -- Daily job ----------------------------------------------------------------

async def run_daily_job() -> None:
    """
    Daily notification-monitoring workflow:
      1. Launch browser and load corp_auth_state.json  [PHANTOM]
      2. Fetch unread-notification delta via XHR       [WARDEN]
      3. Alert on Telegram if new activity found       [HERALD]
      4. Send daily summary                            [HERALD]
      5. Close browser
    """
    logger.info("=" * 60)
    logger.info("WARDEN daily job -- %s", datetime.now().isoformat())
    logger.info("=" * 60)

    herald  = None
    browser = None

    try:
        Config.validate()

        if Config.TG_BOT_TOKEN and Config.TG_CHAT_ID:
            herald = TelegramNotifier(Config.TG_BOT_TOKEN, Config.TG_CHAT_ID)

        # Step 1: PHANTOM -- load saved cookies
        logger.info("Step 1 -- PHANTOM: loading corp_auth_state.json")
        try:
            browser, page = await get_authenticated_page(headless=Config.HEADLESS)
        except Exception as exc:
            logger.error("PHANTOM failed: %s", exc)
            if herald:
                await herald.send_login_failure_alert()
            return

        # Step 2: WARDEN -- check notification count delta
        logger.info("Step 2 -- WARDEN: checking notification count")
        result = await check_and_compare(page, Config.DB_PATH)

        if result.unread_count < 0:
            logger.error("WARDEN: could not fetch notification count")
            if herald:
                await herald.send_error_alert("WARDEN: notification count fetch failed")
        else:
            logger.info(
                "WARDEN: count=%d prev=%d delta=%d new_activity=%s",
                result.unread_count, result.prev_count,
                result.delta, result.has_new_activity,
            )

        # Step 3: HERALD -- new activity alert
        if result.has_new_activity and result.delta > 0 and herald:
            logger.info("Step 3 -- HERALD: sending new activity alert (delta=%d)", result.delta)
            await herald.send_reply_alert(
                candidate_name  = f"{result.delta} new notification(s)",
                position        = "104 Corporate Portal",
                reply_preview   = (
                    f"You have {result.unread_count} unread notifications "
                    f"(+{result.delta} since last check)."
                ),
                job_link        = Config.MSG_CENTER_URL,
            )
        else:
            logger.info("Step 3 -- HERALD: no new activity, skipping alert")

        # Step 4: HERALD -- daily summary
        if herald:
            await herald.send_daily_summary(
                sent_count    = 0,       # COURIER disabled (ASM required)
                replies_count = result.delta if result.delta > 0 else 0,
            )

    except Exception as exc:
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        if herald:
            await herald.send_error_alert(str(exc)[:200])
    finally:
        if browser:
            await close_browser(browser)
        if herald:
            await herald.close()
        logger.info("Daily job complete -- %s", datetime.now().isoformat())
        logger.info("=" * 60)


# -- Scheduler ----------------------------------------------------------------

def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=Config.SCHEDULE_TZ)
    try:
        h, m = map(int, Config.SCHEDULE_TIME.split(":"))
    except ValueError:
        h, m = 9, 0
    scheduler.add_job(
        run_daily_job,
        trigger="cron", hour=h, minute=m,
        timezone=Config.SCHEDULE_TZ,
        id="daily_notification_check",
        misfire_grace_time=600,
    )
    logger.info("Scheduler: daily at %02d:%02d %s", h, m, Config.SCHEDULE_TZ)
    return scheduler


async def main() -> None:
    setup_logging()
    load_dotenv()
    logger.info("WARDEN Orchestrator starting...")
    scheduler = build_scheduler()
    scheduler.start()
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("WARDEN stopped.")


if __name__ == "__main__":
    asyncio.run(main())
