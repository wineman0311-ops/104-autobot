# PHANTOM Browser Module -- 104 Corporate Portal Login
# Uses corp_auth_state.json (bsignin.104.com.tw) to bypass MFA
import asyncio, logging, os, random
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext, TimeoutError as PWTimeout
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DIR            = os.path.dirname(os.path.abspath(__file__))
CORP_AUTH      = os.path.join(DIR, "corp_auth_state.json")
BSIGNIN_URL    = "https://bsignin.104.com.tw/login"
PORTAL_URL     = "https://pro.104.com.tw/hrsystem"
USER_AGENT     = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

async def random_delay(min_s: float = 1.0, max_s: float = 3.0) -> None:
    await asyncio.sleep(random.uniform(min_s, max_s))

async def launch_browser(headless: bool = True) -> tuple[Browser, BrowserContext, Page]:
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=headless,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    ctx_kwargs = dict(
        user_agent=USER_AGENT,
        viewport={"width": 1280, "height": 800},
        locale="zh-TW",
        timezone_id="Asia/Taipei",
    )
    if os.path.exists(CORP_AUTH):
        ctx_kwargs["storage_state"] = CORP_AUTH
        logger.info("PHANTOM: corp_auth_state.json loaded (MFA bypass active)")
    else:
        logger.warning("PHANTOM: corp_auth_state.json not found -- full login required")

    context = await browser.new_context(**ctx_kwargs)
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    page = await context.new_page()
    logger.info("Browser launched (headless=%s)", headless)
    return browser, context, page

async def close_browser(browser: Browser) -> None:
    try:
        await browser.close()
        logger.info("Browser closed")
    except Exception as exc:
        logger.warning("Error closing browser: %s", exc)

async def is_logged_in(page: Page) -> bool:
    """Use URL-redirect detection: if final URL is NOT on bsignin, we are logged in."""
    cur = page.url
    not_logged_in = (
        "bsignin.104.com.tw" in cur and "/login" in cur
    ) or (
        "bsignin.104.com.tw/mfa" in cur
    )
    return not not_logged_in

async def login_104(page: Page, username: str, password: str) -> bool:
    """
    Navigate to corporate portal. If auth_state is valid, stays logged in.
    Falls back to full credential login if session expired.
    """
    logger.info("PHANTOM: navigating to %s", PORTAL_URL)
    await page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=20000)
    await asyncio.sleep(3)
    logger.info("PHANTOM: landed on %s", page.url)

    # URL-based login check: stayed on pro.104 = logged in
    if "bsignin" not in page.url and "signin" not in page.url:
        logger.info("PHANTOM: authenticated via saved cookies (URL: %s)", page.url)
        return True

    logger.info("PHANTOM: session expired -- performing full corporate login")
    await page.goto(BSIGNIN_URL, wait_until="domcontentloaded", timeout=20000)
    await asyncio.sleep(2)

    await page.wait_for_selector("input[name='email']", state="visible", timeout=8000)
    await page.locator("input[name='email']").first.fill(username)
    await random_delay(0.4, 0.8)
    await page.wait_for_selector("input[type='password']", state="visible", timeout=5000)
    await page.locator("input[type='password']").first.fill(password)
    await random_delay(0.4, 0.8)
    await page.locator("button.btn.btn-primary").first.click()
    await asyncio.sleep(4)

    if "mfa" in page.url.lower():
        logger.error("PHANTOM: MFA required -- corp_auth_state.json expired. Re-run corp_phase1.py + corp_phase2.py")
        raise RuntimeError("Corporate MFA required -- please refresh corp_auth_state.json")

    if "bsignin" not in page.url:
        logger.info("PHANTOM: full corporate login successful")
        return True

    await page.screenshot(path=os.path.join(DIR, "corp_login_failure.png"))
    raise RuntimeError("Corporate login failed -- screenshot saved")

async def get_authenticated_page(
    username: Optional[str] = None,
    password: Optional[str] = None,
    headless: bool = True,
) -> tuple[Browser, Page]:
    username = username or os.getenv("ACCOUNT_EMAIL", "")
    password = password or os.getenv("ACCOUNT_PASSWORD", "")
    if not username or not password:
        raise ValueError("ACCOUNT_EMAIL and ACCOUNT_PASSWORD must be set in .env")
    browser, _ctx, page = await launch_browser(headless=headless)
    await login_104(page, username, password)
    return browser, page

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    async def _smoke():
        browser, page = await get_authenticated_page(headless=True)
        print("URL:", page.url)
        print("Logged in:", await is_logged_in(page))
        await asyncio.sleep(2)
        await close_browser(browser)
    asyncio.run(_smoke())
