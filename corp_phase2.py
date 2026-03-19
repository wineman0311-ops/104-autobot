# Corp Phase 2: Restore corp session, fill OTP from otp.txt, save corp_auth_state.json
import asyncio, os, sys, json
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

DIR          = os.path.dirname(os.path.abspath(__file__))
CORP_SESSION = os.path.join(DIR, "corp_mfa_session.json")
CORP_AUTH    = os.path.join(DIR, "corp_auth_state.json")
OTP_FILE     = os.path.join("C:\\Users\\zixuan", "otp.txt")

def log(m): sys.stdout.write(m.encode("ascii","replace").decode()+"\n"); sys.stdout.flush()

async def run():
    # Read OTP
    otp_code = ""
    if os.path.exists(OTP_FILE):
        with open(OTP_FILE) as f:
            otp_code = f.read().strip()
    if not (otp_code and len(otp_code)==6 and otp_code.isdigit()):
        log("ERROR: No valid 6-digit OTP in otp.txt (got: '" + otp_code + "')"); return

    if not os.path.exists(CORP_SESSION):
        log("ERROR: corp_mfa_session.json not found -- run corp_phase1.py first"); return

    with open(CORP_SESSION) as f:
        session = json.load(f)
    mfa_url      = session["mfa_url"]
    storage_path = session["storage"]

    log("=== Corp Phase 2: Fill OTP + Save Corp Auth State ===")
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
            await pg.screenshot(path=os.path.join(DIR, "corp_p2_error.png"))
            await b.close(); return

        log("MFA page OK -- filling OTP: " + otp_code)
        await pg.wait_for_selector("input[name='otp']", state="visible", timeout=8000)
        otp_el = pg.locator("input[name='otp']").first
        await otp_el.click(); await asyncio.sleep(0.3)
        await otp_el.fill(""); await asyncio.sleep(0.2)
        await otp_el.type(otp_code, delay=80)
        log("  filled: " + await otp_el.input_value())
        await asyncio.sleep(0.5)

        log("Clicking verify...")
        btn = pg.locator("button.btn.btn-primary").first
        old_url = pg.url
        try:
            await btn.click(no_wait_after=True, timeout=10000)
            log("  click sent")
        except PWTimeout:
            log("  timeout OK (navigation in progress)")
        except Exception as ex:
            log("  ex: " + str(ex)[:80])

        # Poll for URL change -- confirms OTP accepted
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
            await pg.screenshot(path=os.path.join(DIR, "corp_p2_rejected.png"))
            await b.close(); return

        await asyncio.sleep(3)
        log("Final URL: " + pg.url)
        await pg.screenshot(path=os.path.join(DIR, "corp_p2_success.png"))

        # Handle activate page
        if "activate" in pg.url:
            log("Activation page -- clicking confirm...")
            for sel in ["button.btn.btn-primary","a.btn-primary","button[type='submit']"]:
                try:
                    el = pg.locator(sel).first
                    if await el.count():
                        await el.click(no_wait_after=True, timeout=5000); break
                except Exception: pass
            await asyncio.sleep(4)
            log("URL after activation: " + pg.url)

        # Save corporate auth state
        log("Saving corp_auth_state.json...")
        await ctx.storage_state(path=CORP_AUTH)
        sz = os.path.getsize(CORP_AUTH)
        with open(CORP_AUTH, encoding="utf-8") as f:
            state = json.load(f)
        cookies = state.get("cookies", [])
        corp104 = [c for c in cookies if "104.com" in c.get("domain","")]
        domains = list(set(c.get("domain","") for c in corp104))
        log("Saved! size=" + str(sz) + "b  total=" + str(len(cookies)) + "  104_auth=" + str(len(corp104)))
        log("domains: " + str(domains))

        # Verify by navigating to pro.104.com.tw
        log("Verifying on pro.104.com.tw...")
        await pg.goto("https://pro.104.com.tw/", wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(3)
        final = pg.url
        log("pro.104.com.tw final URL: " + final)
        await pg.screenshot(path=os.path.join(DIR, "corp_p2_pro104.png"))

        if "bsignin" in final or "signin" in final:
            log("WARNING: Still redirected to signin -- corp_auth_state may be incomplete")
        else:
            log("=== SUCCESS: corp_auth_state.json ready! Corporate portal accessible! ===")
            open(OTP_FILE,"w").write("")

        await b.close()

asyncio.run(run())
