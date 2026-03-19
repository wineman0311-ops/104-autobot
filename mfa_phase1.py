"""
MFA Phase 1: Run login → stop at MFA page → save session state + MFA URL
"""
import asyncio, os, sys, json
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
USERNAME = os.getenv("ACCOUNT_EMAIL", "")
PASSWORD = os.getenv("ACCOUNT_PASSWORD", "")
DIR = os.path.dirname(__file__)
MFA_SESSION = os.path.join(DIR, "mfa_session.json")  # saves URL + storage state

def log(m): sys.stdout.write(m.encode("ascii","replace").decode()+"\n"); sys.stdout.flush()

async def run():
    log("=== Phase 1: Login to MFA page ===")
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="zh-TW",
        )
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        pg = await ctx.new_page()

        log("login step 1/4: goto 104")
        await pg.goto("https://www.104.com.tw/jobs/main/", wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2)
        for sel in ["a[href*='signin']", "a[href*='login']"]:
            el = pg.locator(sel).first
            if await el.count(): await el.click(); break
        await asyncio.sleep(3)

        log("login step 2/4: fill email")
        await pg.wait_for_selector("input[name='identity']", state="visible", timeout=8000)
        await pg.locator("input[name='identity']").first.fill(USERNAME)
        await asyncio.sleep(0.5)
        await pg.locator("button.btn.btn-primary").first.click()
        await asyncio.sleep(3)

        log("login step 3/4: fill password")
        await pg.wait_for_selector("input[type='password']:not([name='fakeInput'])", state="visible", timeout=10000)
        await pg.locator("input[type='password']:not([name='fakeInput'])").first.fill(PASSWORD)
        await asyncio.sleep(0.5)

        log("login step 4/4: submit")
        await pg.locator("button.btn.btn-primary").first.click()
        await asyncio.sleep(3)
        mfa_url = pg.url
        log("url: " + mfa_url)

        if "mfa" not in mfa_url.lower():
            log("ERROR: expected MFA page, got: " + mfa_url)
            await b.close(); return

        log("MFA page confirmed — saving session state")
        # Save storage state (cookies + localStorage)
        state_path = os.path.join(DIR, "mfa_storage.json")
        await ctx.storage_state(path=state_path)

        # Save MFA URL for phase 2
        with open(MFA_SESSION, "w") as f:
            json.dump({"mfa_url": mfa_url, "storage": state_path}, f)

        log("Session saved to mfa_session.json")
        log("MFA URL: " + mfa_url[:80] + "...")
        log("=== Phase 1 DONE — please check your email and run Phase 2 with the code ===")
        await b.close()

asyncio.run(run())
