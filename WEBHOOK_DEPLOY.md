# Translation Bot - Webhook Deployment

This bot runs with webhooks (Telegram pushes updates to your HTTPS URL), perfect for 24/7 serverless hosting.

## Files

- `app.py` - Flask webhook server (replaces `bot.py` for serverless)
- `bot.py` - Original long-polling version (for local PC)
- `translator.py` - Translation logic (unchanged)
- `config.json` - Bot token & settings
- `requirements-webhook.txt` - Dependencies for webhook hosting
- `Procfile` - For Railway/Render
- `package.json` - For some Node-based platforms (not needed)

## Deploy to Railway (free, easy, always-on)

1. Push this folder to GitHub
2. Go to [railway.app](https://railway.app) → Login with GitHub
3. New Project → Deploy from GitHub repo → Select this repo
4. Add environment variable: `BOT_TOKEN` = `<BOT_TOKEN>`
5. Railway will auto-detect and deploy. It gives you a URL like `https://translate-bot-production.up.railway.app/`
6. Set webhook: Open browser with `https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://YOUR-RAILWAY-URL/YOUR-TOKEN` (or just root; app.py accepts both)
7. Done! Bot runs 24/7

## Deploy to Koyeb (free, always-on)

1. Push to GitHub
2. Go to [koyeb.com](https://www.koyeb.com) → Create app from GitHub
3. Build with Python, start: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4`
4. Add env var `BOT_TOKEN`
5. Get public URL, set webhook as above

## Deploy to Cloudflare Workers (free, webhook-only)

Workers can't run Flask directly. Need to use a webhook adapter (e.g. `python-telegram-bot` with webhooks via `fetch`). Simpler: use Railway/Koyeb.

## Set webhook manually

After getting your public HTTPS URL (e.g. `https://your-app.railway.app`), run:
```text
https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://your-app.railway.app/<BOT_TOKEN>
```

Check: `https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo`

## Local test (optional)

```bash
set PORT=5000
python app.py
```

Then use ngrok to expose: `ngrok http 5000` and set webhook to ngrok URL.
