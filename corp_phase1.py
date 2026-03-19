# Corp Phase 1: Login to bsignin.104.com.tw -> reach MFA -> save session
import asyncio, os, sys, json
from dotenv import load_dotenv
from playwright.async_api import async_playwright

DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(DIR, ".env"))
EMAIL    = os.getenv("ACCOUNT_EMAIL", "")
PASSWORD = os.getenv("ACCOUNT_PASSWORD", "")
CORP_SESSION = os.path.join(DIR, "corp_mfa_session.json")

def log(m): sys.stdout.write(m.encode("ascii","replace").decode()+"\n"); sys.stdout.flush()

async def run():
    log("=== Corp Phase 1: bsignin.104.com.tw Login ===")
    log("Email: " + EMAIL)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="zh-TW",
        )
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        pg = await ctx.new_page()

        log("Step 1: Navigate to bsignin login page...")
        await pg.goto("https://bsignin.104.com.tw/login", wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2)
        log("URL: " + pg.url)

        log("Step 2: Fill email + password (single-step form)...")
        await pg.wait_for_selector("input[name='email']", state="visible", timeout=8000)
        await pg.locator("input[name='email']").first.fill(EMAIL)
        await asyncio.sleep(0.4)
        await pg.wait_for_selector("input[type='password']", state="visible", timeout=5000)
        await pg.locator("input[type='password']").first.fill(PASSWORD)
        await asyncio.sleep(0.4)

        log("Step 3: Click login button...")
        await pg.locator("button.btn.btn-primary").first.click()
        await asyncio.sleep(4)
        log("URL after submit: " + pg.url)

        if "mfa" not in pg.url.lower():
            log("ERROR: Expected MFA page, got: " + pg.url)
            await pg.screenshot(path=os.path.join(DIR, "corp_p1_error.png"))
            await b.close(); return

        log("MFA page confirmed! Saving session...")
        mfa_url = pg.url
        storage_path = os.path.join(DIR, "corp_mfa_storage.json")
        await ctx.storage_state(path=storage_path)
        with open(CORP_SESSION, "w") as f:
            json.dump({"mfa_url": mfa_url, "storage": storage_path}, f)

        log("corp_mfa_session.json saved")
        log("MFA URL: " + mfa_url[:80] + "...")
        log("=== CHECK YOUR EMAIL for OTP, then write it to otp.txt and run corp_phase2.py ===")
        await b.close()

asyncio.run(run())
