"""
SCOUT Searcher Module -- 104 Candidate Search & Filter

IMPORTANT -- ASM ACTIVATION REQUIRED:
  Proactive talent-pool search requires the ASM (Advanced Search Module) to be
  activated on the corporate account (userWidgetPermit.asm.company == 'on').
  This account currently has asm.company='none', asm.user='off'.
  Contact 104 business support to activate ASM.

  Once ASM is activated:
    - Candidate search URL: https://pro.104.com.tw/asm/resume
    - Invite URL:           https://pro.104.com.tw/asm/invite
    - Message center:       https://pro.104.com.tw/asm/message

  This module currently returns an empty list to allow the pipeline to run
  without crashing. When ASM is activated, replace the stub with real logic.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import Page

logger = logging.getLogger(__name__)

ASM_RESUME_URL = "https://pro.104.com.tw/asm/resume"
ASM_ACTIVE_PERMIT_VALUE = "on"


@dataclass
class CandidateFilter:
    """Filter criteria for candidate search on 104 portal."""
    education_min: str = ""          # e.g. "大學", "碩士"
    experience_years_min: int = 0
    location: str = ""               # e.g. "台北市"
    language: str = ""               # e.g. "英文"
    keywords: list[str] = field(default_factory=list)


@dataclass
class Candidate:
    """Candidate data extracted from search results."""
    candidate_id: str
    name: str
    age: Optional[int]
    education: str
    experience_years: int
    location: str
    last_active: str
    profile_url: str

    def __repr__(self) -> str:
        return (
            f"Candidate(id={self.candidate_id}, name={self.name}, "
            f"age={self.age}, exp={self.experience_years}y, loc={self.location})"
        )


def _check_asm_active(page_user_js: dict) -> bool:
    """Check if ASM module is activated from the page's user object."""
    try:
        permit = page_user_js.get("userWidgetPermit", {})
        return permit.get("asm", {}).get("company") == ASM_ACTIVE_PERMIT_VALUE
    except Exception:
        return False


async def is_asm_activated(page: Page) -> bool:
    """
    Check whether ASM is activated for this account by reading the JS user object.
    Returns True only when asm.company == 'on'.
    """
    try:
        user_json = await page.evaluate(
            "() => typeof user !== 'undefined' ? JSON.stringify(user) : '{}'"
        )
        import json
        user_obj = json.loads(user_json)
        active = _check_asm_active(user_obj)
        if not active:
            logger.warning(
                "SCOUT -> ASM not activated (company=%s user=%s). "
                "Contact 104 to activate talent pool search.",
                user_obj.get("userWidgetPermit", {}).get("asm", {}).get("company", "?"),
                user_obj.get("userWidgetPermit", {}).get("asm", {}).get("user", "?"),
            )
        return active
    except Exception as exc:
        logger.error("SCOUT -> is_asm_activated error: %s", exc)
        return False


async def search_candidates(
    page: Page,
    filters: CandidateFilter,
    max_results: int = 20,
) -> list[Candidate]:
    """
    Search 104 talent pool. Returns empty list if ASM is not activated.

    Args:
        page:        Authenticated Playwright page (must already be on pro.104.com.tw).
        filters:     CandidateFilter with search criteria.
        max_results: Maximum candidates to collect.

    Returns:
        List of Candidate objects, or [] when ASM is not activated.
    """
    active = await is_asm_activated(page)
    if not active:
        logger.warning("SCOUT -> ASM not active; returning empty candidate list.")
        return []

    # ── Real implementation (only reached when ASM is activated) ─────────────
    logger.info("SCOUT -> ASM active; navigating to talent search")
    candidates: list[Candidate] = []
    try:
        await page.goto(ASM_RESUME_URL, wait_until="networkidle", timeout=20000)
        import asyncio
        await asyncio.sleep(2)
        # TODO: implement filter application + multi-page scraping once ASM is live
        logger.info("SCOUT -> ASM search placeholder; implement selectors after activation")
    except Exception as exc:
        logger.error("SCOUT -> search_candidates error: %s", exc)

    return candidates


def filter_already_contacted(candidates: list[Candidate], contacted_ids: set) -> list[Candidate]:
    """Remove candidates already in the contacted set."""
    filtered = [c for c in candidates if c.candidate_id not in contacted_ids]
    logger.info(
        "Filtered %d already-contacted; %d remaining",
        len(candidates) - len(filtered),
        len(filtered),
    )
    return filtered


def load_sent_ids(db_path: str) -> set[str]:
    """Load previously contacted candidate IDs from SQLite."""
    import sqlite3
    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS sent_messages (
        candidate_id   TEXT PRIMARY KEY,
        sent_at        TEXT NOT NULL,
        position_title TEXT NOT NULL
    );
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(_SCHEMA)
        conn.commit()
        ids = {row[0] for row in conn.execute("SELECT candidate_id FROM sent_messages")}
        conn.close()
        logger.info("Loaded %d contacted IDs from %s", len(ids), db_path)
        return ids
    except sqlite3.Error as exc:
        logger.error("DB load error: %s", exc)
        return set()
