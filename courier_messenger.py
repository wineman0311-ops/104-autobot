"""
COURIER Messenger Module -- 104 Internal Message Sender

IMPORTANT -- ASM ACTIVATION REQUIRED:
  Proactive candidate invitations require the ASM (Advanced Search Module).
  This account currently has asm.company='none', asm.user='off'.
  Contact 104 business support to activate ASM.

  Once ASM is activated:
    - Invite URL: https://pro.104.com.tw/asm/invite
    - Selectors (to verify after activation):
        button:has-text('主動邀約')  /  button:has-text('寄送訊息')
        [data-qa='invite-btn']  /  a:has-text('聯絡求職者')

  This module currently returns empty results to allow the pipeline to run
  without crashing. When ASM is activated, restore the original implementation.
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional

from playwright.async_api import Page

logger = logging.getLogger(__name__)

try:
    from scout_searcher import Candidate
except ImportError:
    @dataclass
    class Candidate:  # type: ignore[no-redef]
        candidate_id: str
        name: str
        age: Optional[int]
        education: str
        experience_years: int
        location: str
        last_active: str
        profile_url: str


class DailyLimitError(Exception):
    """Raised when the daily message quota has been exhausted."""


@dataclass
class MessageTemplate:
    subject: str
    body: str           # supports {candidate_name} and {position}
    position_title: str

    def format_message(self, candidate_name: str) -> str:
        return self.body.format(candidate_name=candidate_name,
                                position=self.position_title)


@dataclass
class MessageResult:
    candidate_id: str
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    error_msg: Optional[str] = None


# -- Rate limiter -------------------------------------------------------------

class MessageLimiter:
    def __init__(self, daily_max: int = 30):
        self._daily_max  = daily_max
        self._sent_today = 0
        self._reset_date = date.today()

    def _maybe_reset(self) -> None:
        if date.today() != self._reset_date:
            self._sent_today = 0
            self._reset_date = date.today()

    @property
    def remaining(self) -> int:
        self._maybe_reset()
        return max(0, self._daily_max - self._sent_today)

    def record_sent(self) -> None:
        self._maybe_reset()
        self._sent_today += 1

    def is_limit_reached(self) -> bool:
        return self.remaining == 0


_limiter = MessageLimiter()


def set_daily_message_limit(n: int) -> None:
    _limiter._daily_max = n


def get_remaining_messages() -> int:
    return _limiter.remaining


# -- Core (stub) --------------------------------------------------------------

async def send_message(
    page: Page,
    candidate: "Candidate",
    template: MessageTemplate,
) -> MessageResult:
    """
    Send an invite message to a candidate.
    Currently a stub -- returns failure because ASM is not activated.
    """
    logger.warning(
        "COURIER -> send_message called but ASM is not activated. "
        "Activate ASM at https://pro.104.com.tw/admin/users to enable messaging."
    )
    return MessageResult(
        candidate.candidate_id, False,
        error_msg="ASM not activated -- proactive messaging unavailable"
    )


async def batch_send_messages(
    page: Page,
    candidates: list["Candidate"],
    template: MessageTemplate,
    inter_message_delay: tuple[float, float] = (3.0, 7.0),
) -> list[MessageResult]:
    """Batch send -- returns empty results when ASM is not activated."""
    if not candidates:
        return []
    logger.warning(
        "COURIER -> batch_send_messages: %d candidates queued but ASM not activated. "
        "Returning empty results.", len(candidates)
    )
    return [
        MessageResult(c.candidate_id, False,
                      error_msg="ASM not activated")
        for c in candidates
    ]
