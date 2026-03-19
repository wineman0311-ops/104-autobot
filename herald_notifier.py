"""
HERALD Notifier Module — Telegram Bot Alerts
PoC: Sends recruitment-event notifications via Telegram Bot API (v20+ async).
"""

import asyncio
import logging
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError, InvalidToken

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Sends structured Telegram notifications for recruitment events."""

    def __init__(self, bot_token: str, chat_id: str):
        if not bot_token or not chat_id:
            raise ValueError("bot_token and chat_id must not be empty")
        self.bot_token   = bot_token
        self.chat_id     = chat_id
        self.bot         = Bot(token=bot_token)
        self.max_retries = 3
        self.base_delay  = 1
        logger.info("HERALD initialised for chat_id=%s", chat_id)

    async def _send(self, text: str) -> bool:
        for attempt in range(self.max_retries):
            try:
                await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="HTML")
                return True
            except InvalidToken as exc:
                logger.error("Invalid Telegram token: %s", exc)
                return False
            except TelegramError as exc:
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning("TG error attempt %d/%d: %s — retry in %ds",
                                   attempt + 1, self.max_retries, exc, delay)
                    await asyncio.sleep(delay)
                else:
                    logger.error("Failed after %d attempts: %s", self.max_retries, exc)
                    return False
        return False

    async def send_reply_alert(
        self,
        candidate_name: str,
        position: str,
        reply_preview: str,
        job_link: str = "https://www.104.com.tw",
    ) -> bool:
        preview = (reply_preview[:120] + "…") if len(reply_preview) > 120 else reply_preview
        text = (
            "🔔 <b>新回覆通知</b>\n"
            f"👤 候選人：<code>{candidate_name}</code>\n"
            f"💼 職缺：<code>{position}</code>\n"
            f"💬 回覆摘要：{preview}\n\n"
            f"請上 104 查看完整訊息 👉 <a href='{job_link}'>點此開啟</a>"
        )
        logger.info("HERALD → reply alert for %s", candidate_name)
        return await self._send(text)

    async def send_error_alert(self, error_msg: str) -> bool:
        text = (
            "⚠️ <b>系統錯誤通知</b>\n"
            f"<code>{error_msg}</code>\n\n"
            "請檢查系統狀態。"
        )
        logger.warning("HERALD → error alert: %s", error_msg)
        return await self._send(text)

    async def send_daily_summary(self, sent_count: int, replies_count: int) -> bool:
        text = (
            "📊 <b>每日統計摘要</b>\n"
            f"✉️ 今日已發送：<b>{sent_count}</b> 則\n"
            f"💬 收到有效回覆：<b>{replies_count}</b> 則\n\n"
            "祝招募順利！"
        )
        logger.info("HERALD → daily summary sent=%d replies=%d", sent_count, replies_count)
        return await self._send(text)

    async def send_login_failure_alert(self) -> bool:
        text = (
            "🚨 <b>登入失敗警示</b>\n"
            "自動登入 104 失敗，可能原因：\n"
            "• 帳號或密碼錯誤\n"
            "• 網路問題或伺服器暫停\n"
            "• 需要 CAPTCHA 人工驗證\n\n"
            "請手動登入確認狀態。"
        )
        logger.error("HERALD → login failure alert")
        return await self._send(text)

    async def close(self) -> None:
        try:
            await self.bot.session.close()
        except Exception:
            pass
