# 104 AutoBot

Automated recruitment assistant for the 104.com.tw corporate portal.
Monitors unread notifications and sends Telegram alerts via a daily scheduled job.

## Architecture

| Module | File | Status |
|--------|------|--------|
| PHANTOM | `phantom_browser.py` | ✅ Cookie-based MFA bypass |
| WARDEN | `warden_checker.py` | ✅ Notification count monitor |
| HERALD | `herald_notifier.py` | ✅ Telegram push alerts |
| SCOUT | `scout_searcher.py` | ⚠️ Requires ASM activation |
| COURIER | `courier_messenger.py` | ⚠️ Requires ASM activation |

## How it works

1. **PHANTOM** loads `corp_auth_state.json` (saved corporate portal cookies) and authenticates to `pro.104.com.tw/hrsystem` without triggering MFA.
2. **WARDEN** calls the internal `commons/api/countUnreadNotification` API via XHR and compares the count to the last saved value.
3. **HERALD** sends a Telegram message via `@Assistant_104Bot` when the count increases.
4. The job runs daily at 09:00 Asia/Taipei via APScheduler.

## Deployment (Zeabur)

### 1. Encode your auth state locally

```bash
py encode_auth.py
# Copy the base64 output
```

### 2. Create Zeabur service from this GitHub repo

- Go to [zeabur.com](https://zeabur.com) → New Project → Deploy from GitHub
- Select this repository
- Zeabur will detect the `Dockerfile` automatically

### 3. Set environment variables on Zeabur

| Variable | Value |
|----------|-------|
| `CORP_AUTH_STATE_JSON` | base64 output from `encode_auth.py` |
| `ACCOUNT_EMAIL` | your 104 login email |
| `ACCOUNT_PASSWORD` | your 104 password |
| `TG_BOT_TOKEN` | your Telegram bot token |
| `TG_CHAT_ID` | your Telegram chat ID |
| `SCHEDULE_TIME` | e.g. `09:00` |
| `SCHEDULE_TIMEZONE` | `Asia/Taipei` |
| `HEADLESS` | `true` |

### 4. Redeploy after env vars are set

Every `git push` to `main` will trigger a new Zeabur build automatically.

## Re-authentication (when cookies expire)

Corporate portal cookies last ~30 days. When they expire:

```bash
py corp_phase1.py      # triggers OTP email
# Enter OTP when prompted
py corp_phase2.py      # saves new corp_auth_state.json
py encode_auth.py      # re-generate base64
# Update CORP_AUTH_STATE_JSON on Zeabur dashboard → Redeploy
```

## ASM Activation (for full recruitment features)

To enable proactive candidate search (SCOUT) and messaging (COURIER):
- Contact 104 business support: 02-2912-6104 ext. 6100
- Once activated, SCOUT and COURIER will enable automatically (`asm.company == "on"`)
