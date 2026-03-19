# Phase 2: Restore mfa_session.json, fill OTP from otp.txt, wait for navigation, save auth_state.json
import asyncio, os, sys, json
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

DIR         = os.path.dirname(os.path.abspath(__file__))
MFA_SESSION = os.path.join(DIR, "mfa_session.json")
AUTH_STATE  = os.path.join(DIR, "auth_state.json")
OTP_FILE    = os.path.join("C:\\Users\\zixuan", "otp.txt")

def log(m): sys.stdout.write(m.encode("ascii","replace").decode()+"\n"); sys.stdout.flush()

async def run():
    otp_code = ""
    if os.path.exists(OTP_FILE):
        with open(OTP_FILE) as f:
            otp_code = f.read().strip()
    if not (otp_code and len(otp_code)==6 and otp_code.isdigit()):
        log("ERROR: No valid 6-digit OTP in otp.txt (got: '" + otp_code + "')"); return

    if not os.path.exists(MFA_SESSION):
        log("ERROR: mfa_session.json not found -- run mfa_phase1.py first"); return

    with open(MFA_SESSION) as f:
        session = json.load(f)
    mfa_url      = session["mfa_url"]
    storage_path = session["storage"]

    log("=== Phase 2: Fill OTP + Save Auth State ===")
    log("OTP: " + otp_code)

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(
            storage_state=storage_path,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="zh-TW",
        )
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        pg = await ctx.new_page()

        log("Restoring MFA session...")
        await pg.goto(mfa_url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(3)
        log("URL: " + pg.url)

        if "mfa" not in pg.url.lower():
            log("ERROR: Not on MFA page: " + pg.url)
            await pg.screenshot(path=os.path.join(DIR, "p2_error.png"))
            await b.close(); return

        log("MFA page OK -- filling OTP...")
        await pg.wait_for_selector("input[name='otp']", state="visible", timeout=8000)
        otp_el = pg.locator("input[name='otp']").first
        await otp_el.click(); await asyncio.sleep(0.3)
        await otp_el.fill(""); await asyncio.sleep(0.2)
        await otp_el.type(otp_code, delay=80)
        log("  filled: " + await otp_el.input_value())
        await asyncio.sleep(0.5)

        log("Submitting OTP...")
        btn = pg.locator("button.btn.btn-primary").first
        old_url = pg.url
        try:
            await btn.click(no_wait_after=True, timeout=10000)
            log("  click sent")
        except PWTimeout:
            log("  timeout OK (navigation in progress)")
        except Exception as ex:
            log("  ex: " + str(ex)[:80])

        # Poll for URL change (up to 20 seconds) -- confirms OTP accepted
        navigated = False
        for i in range(20):
            await asyncio.sleep(1)
            cur = pg.url
            if cur != old_url:
                log("  navigated after " + str(i+1) + "s -> " + cur[:80])
                navigated = True
                break

        if not navigated:
            log("ERROR: URL did not change -- OTP rejected or session expired")
            await pg.screenshot(path=os.path.join(DIR, "p2_rejected.png"))
            await b.close(); return

        await asyncio.sleep(3)
        log("Final URL: " + pg.url)
        await pg.screenshot(path=os.path.join(DIR, "p2_success.png"))

        # Handle activate page if present
        if "activate" in pg.url:
            log("Activation page -- handling...")
            for sel in ["button.btn.btn-primary","a.btn-primary","button[type='submit']"]:
                try:
                    el = pg.locator(sel).first
                    if await el.count():
                        await el.click(no_wait_after=True, timeout=5000); break
                except Exception: pass
            await asyncio.sleep(4)
            log("URL after activation: " + pg.url)

        # Save auth state
        log("Saving auth_state.json...")
        await ctx.storage_state(path=AUTH_STATE)
        sz = os.path.getsize(AUTH_STATE)
        with open(AUTH_STATE, encoding="utf-8") as f:
            state = json.load(f)
        cookies = state.get("cookies", [])
        auth104 = [c for c in cookies if "104.com" in c.get("domain","")]
        domains = list(set(c.get("domain","") for c in auth104))
        log("Saved! size=" + str(sz) + "b  total=" + str(len(cookies)) + "  104_auth=" + str(len(auth104)))
        log("104 domains: " + str(domains))

        if auth104:
            log("=== SUCCESS: auth_state.json ready! ===")
            open(OTP_FILE,"w").write("")
        else:
            log("WARNING: no 104 cookies in auth_state")

        await b.close()

asyncio.run(run())
