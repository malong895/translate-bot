# Translation Bot - 24/7 Cloud Deployment

Two free ways to keep the bot online even when your PC is off.

The bot's `app.py` (webhook server) **auto-registers the Telegram webhook on
startup** using the platform's public URL, so no manual webhook step is needed.

- `app.py` - Flask webhook server (cloud)
- `bot.py` - Long-polling version (local PC)
- `service_runner.py` - Local 24/7 supervisor (auto-restart, single instance)
- `render.yaml` - One-click Render blueprint
- `.github/workflows/keep-alive.yml` - Pings the Render app so the free tier
  never sleeps

---

## Option 1 - Render (free, no card) - RECOMMENDED

Same platform your `itbot` already uses 24/7.

1. Go to https://dashboard.render.com → **New** → **Blueprint**
2. Connect the GitHub repo **malong895/translate-bot** (private)
3. Render reads `render.yaml` and creates the `translatebot` web service
4. Set the env var **BOT_TOKEN** = your BotFather token, then **Apply**
5. Wait for "Live", copy the URL (e.g. `https://translatebot.onrender.com`)
6. Add it as a GitHub repo secret named **RENDER_URL** (Settings → Secrets →
   Actions) so the keep-alive workflow keeps it awake
7. Done - runs 24/7 with your PC off

## Option 2 - Oracle Cloud Always Free VPS ($0 forever)

If the Oracle instance is created, deploy with one command:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy-translatebot-to-vps.ps1 -VpsIp THE_IP
```

This installs `translatebot.service` (systemd, auto-restart) and stops the
local copy so you don't get double replies.

## Option 3 - Railway / Koyeb (free tiers)

- New project → Deploy from GitHub repo `malong895/translate-bot`
- Build: `pip install -r requirements-webhook.txt`
- Start: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`
- Set env var `BOT_TOKEN`

---

## Important rules

- The bot must NOT run on the PC and in the cloud at the same time (double
  replies). After cloud deploy: stop the local task
  (`Stop-ScheduledTask -TaskName "TranslateBot"`).
- Never commit `config.json` (contains the token); it is git-ignored.

## Manual webhook check

`https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo`
