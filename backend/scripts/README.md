# Live Etimad fetch — local runner

Etimad sits behind an **F5 / Shape WAF**. It cannot be beaten by a plain HTTP
client or a re-launched headless browser: the JavaScript challenge issues a
clearance cookie bound to the **client IP + User-Agent**. The only pattern that
reliably works — confirmed across similar projects — is:

> **capture once → reuse the cookies → keep the session warm.**

Run everything below **from the machine/IP you want the clearance tied to** — your
own PC or a **Saudi VPS**. Foreign cloud IPs (Render/Vercel/GitHub Actions) get
`Request Rejected`, which is why this is a *local* runner, not a server job.

## One-time setup

```bash
pip install -r requirements-fetch.txt
python -m playwright install chromium         # only needed for --login capture
```

Set the destination database once (or let `setup_fetch.ps1` persist it to `.env`):

```bash
export DATABASE_URL='postgresql://...neon.tech/neondb?sslmode=require'   # macOS/Linux
$env:DATABASE_URL='postgresql://...neon.tech/neondb?sslmode=require'     # Windows
```

## Recommended: authenticated session (best F5 survival)

```bash
# 1) Sign in ONCE in a real browser. We snapshot the cookie jar (F5 TSPD + auth
#    cookies) to etimad_cookies.json. Approve Nafath on your phone if prompted.
python scripts/fetch_live.py --login

# 2) Fetch by REUSING those cookies. A keep-alive ping every ~60s keeps the F5
#    clearance warm, so the jar stays valid for hours with no browser relaunch.
python scripts/fetch_live.py --session            # incremental
python scripts/fetch_live.py --session --full     # full walk (first backfill)
```

Optional credential **prefill** (the browser still opens so you can finish
Nafath/OTP) — never commit these:

```bash
export ETIMAD_USERNAME='...'
export ETIMAD_PASSWORD='...'
```

When cookies expire (or you move to a different IP), just re-run `--login` on the
same machine.

## Other modes

```bash
python scripts/fetch_live.py --dry-run    # one page, printed, no DB writes
python scripts/fetch_live.py              # browser-per-run (no saved session)
python scripts/fetch_live.py --http       # plain HTTP (usually dies after page 1)
```

## Automating the daily run

- **Windows:** Task Scheduler → daily → `py -3.12 scripts\fetch_live.py --session`
- **Linux/VPS:** cron → `0 3 * * * cd /path/backend && python scripts/fetch_live.py --session`

`etimad_cookies.json`, `.env`, and any `cookies*.json` are git-ignored — they
hold live credentials and must never be committed.
