# Translation Bot (@IT5TRBOT)

A Telegram bot that translates group messages both ways between two languages
chosen per group.

Example: a group is set to **Chinese Simplified ↔ English**.

- `hello` → bot replies `你好`
- `How are you ?` → bot replies `你好吗？`
- `请检查我的网络` → bot replies `Please check my network`

Each group keeps its own 2-language set.

## Setup (one time)

1. **Disable privacy mode** so the bot can read normal group messages:
   - Open [@BotFather](https://t.me/BotFather) → `/mybots` → `IT.TranslateBOT`
   - `Bot Settings` → `Group Privacy` → **Turn off**
   - Without this the bot is silent in groups.

2. Add the bot to your group (as a normal member is enough).

3. Start the bot: double-click `run.bat`.

4. In the group send `/start`, tap the two languages (e.g. `Chinese Simplified`
   and `English`), then tap `💾 Save (2/2)`.

5. Type any message in the group — the bot replies with the translation.

## Commands

- `/start` or `/settings` – open the language picker for the current chat
- `/help` – short help

## Notes

- The message that is in language A is translated to B, and vice versa. The
  direction is decided automatically from the text (script + language detection).
- Translation uses the free MyMemory API (no key). Optional: put an email in
  `mymemory_email` in `config.json` to raise the daily quota. Google Translate is
  used automatically as a fallback if available.
- If the bot is deployed to a server, see the VPS deployment skill.

## Files

- `bot.py` – Telegram handlers, per-group language picker, auto-translation
- `translator.py` – translation backends + direction detection
- `config.json` – bot token, optional email, per-group settings
- `run.bat` – run the bot with the bundled virtualenv
