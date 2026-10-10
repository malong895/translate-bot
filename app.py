# Translation bot - Flask webhook version for serverless hosting

import asyncio
import json
import logging
import os
import threading

from flask import Flask, request, Response
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import translator
from translator import LANGUAGES, LANG_NAME, flag_of

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

COLS = 3

SEED_PATH = os.path.join(BASE_DIR, "seed_config.json")


def _load_config():
    for path in (CONFIG_PATH, SEED_PATH):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, ValueError):
                continue
    return {}


config = _load_config()

BOT_TOKEN = os.environ.get("BOT_TOKEN") or config.get("bot_token")
MYMEMORY_EMAIL = os.environ.get("MYMEMORY_EMAIL") or config.get("mymemory_email") or None
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN is not set (env var or config.json)")

# pending[(chat_id, user_id)] = {"selected": set(codes)}
pending = {}

app = Flask(__name__)


def save_config():
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except OSError as exc:  # noqa: BLE001
        logger.warning("Could not persist config: %s", exc)


def chat_cfg(chat_id):
    return config.setdefault("chat_configs", {}).get(str(chat_id))


# --------------------------------------------------------------------------- #
# Language picker menu
# --------------------------------------------------------------------------- #
def build_menu(selected):
    rows, row = [], []
    for code, name in LANGUAGES:
        mark = "✅ " if code in selected else ""
        row.append(InlineKeyboardButton(f"{flag_of(code)} {mark}{name}", callback_data=f"t|{code}"))
        if len(row) == COLS:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton(f"💾 Save ({len(selected)}/2)", callback_data="save")])
    return InlineKeyboardMarkup(rows)


def menu_text(chat_id):
    current = chat_cfg(chat_id) or {}
    langs = current.get("languages") or []
    lines = [
        "🌐 Translation settings",
        "",
        "Pick 2 languages, then tap Save.",
        "The bot translates between them in both directions.",
    ]
    if len(langs) == 2:
        a, b = LANG_NAME.get(langs[0], langs[0]), LANG_NAME.get(langs[1], langs[1])
        lines += ["", f"Current: {a} ↔️ {b}"]
    return "\n".join(lines)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    key = (chat.id, user.id)

    current = chat_cfg(chat.id) or {}
    selected = set(current.get("languages") or [])
    pending[key] = {"selected": selected}

    sticker = current.get("sticker_file_id")
    if sticker:
        try:
            await update.effective_message.reply_sticker(
                sticker=sticker, reply_markup=build_menu(selected)
            )
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to send saved sticker: %s", exc)

    await update.effective_message.reply_text(
        menu_text(chat.id), reply_markup=build_menu(selected)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Bidirectional translation bot.\n\n"
        "/start - choose 2 languages for this chat\n\n"
        "After saving, just type a message: I translate it into the other "
        "language automatically.\n\n"
        "Note: an admin must turn OFF privacy mode in BotFather so the bot can "
        "read group messages."
    )


# --------------------------------------------------------------------------- #
# Sticker saver
# --------------------------------------------------------------------------- #
async def add_sticker_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg is None:
        return
    if msg.reply_to_message is None:
        await msg.reply_text(
            "Reply to the sticker with /addsticker to save it for this group."
        )
        return
    st = msg.reply_to_message.sticker
    if st is None:
        await msg.reply_text("The replied message is not a sticker.")
        return
    chat_id = str(msg.chat_id)
    config.setdefault("chat_configs", {}).setdefault(chat_id, {})["sticker_file_id"] = st.file_id
    save_config()
    await msg.reply_text("Sticker saved for this group. Next /start will include it.")


async def del_sticker_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    cfg = config.setdefault("chat_configs", {}).get(chat_id, {})
    if cfg.pop("sticker_file_id", None) is not None:
        save_config()
        await update.effective_message.reply_text("Sticker removed.")
    else:
        await update.effective_message.reply_text("No sticker saved in this group.")


# --------------------------------------------------------------------------- #
# Callback handling for the picker
# --------------------------------------------------------------------------- #
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    chat_id = query.message.chat_id
    key = (chat_id, query.from_user.id)
    state = pending.setdefault(key, {"selected": set()})

    if data.startswith("t|"):
        code = data.split("|", 1)[1]
        selected = state["selected"]
        if code in selected:
            selected.discard(code)
        elif len(selected) >= 2:
            await query.answer("You can pick only 2 languages. Deselect one first.", show_alert=True)
            return
        else:
            selected.add(code)
        await query.answer()
        await query.edit_message_reply_markup(build_menu(selected))
        return

    if data == "save":
        selected = state["selected"]
        if len(selected) != 2:
            await query.answer("Please select exactly 2 languages first.", show_alert=True)
            return
        ordered = [code for code, _ in LANGUAGES if code in selected]
        config.setdefault("chat_configs", {})[str(chat_id)] = {"languages": ordered}
        save_config()
        a, b = LANG_NAME[ordered[0]], LANG_NAME[ordered[1]]
        await query.answer("Saved!")
        await query.edit_message_text(
            "✅ Saved for this group:\n\n"
            f"{a} ↔️ {b}\n"
            f"{b} ↔️ {a}\n\n"
            "Now just type in the group and I'll translate automatically."
        )
        return

    await query.answer()


# --------------------------------------------------------------------------- #
# Group message translation
# --------------------------------------------------------------------------- #
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    if msg is None or not msg.text:
        return
    if user is not None and user.is_bot:
        return
    if msg.text.startswith("/"):
        return

    cfg = chat_cfg(msg.chat_id)
    if not cfg:
        return
    langs = cfg.get("languages") or []
    if len(langs) != 2:
        return

    text = msg.text.strip()
    if not text:
        return

    a, b = langs[0], langs[1]
    source = translator.choose_source(text, a, b)
    if source is None:
        return
    target = b if source == a else a

    try:
        await msg.chat.send_action(ChatAction.TYPING)
        translated = await asyncio.to_thread(
            translator.translate, text, source, target, MYMEMORY_EMAIL
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Translation error in chat %s: %s", msg.chat_id, exc)
        return

    if translated and translated.strip() and translated.strip() != text:
        await msg.reply_text(translated)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Update caused error", exc_info=context.error)


# Build application
application = Application.builder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("settings", start_command))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("addsticker", add_sticker_command))
application.add_handler(CommandHandler("delsticker", del_sticker_command))
application.add_handler(CallbackQueryHandler(on_callback))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
application.add_error_handler(error_handler)


WEBHOOK_BASE = (os.environ.get("WEBHOOK_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")


async def _init_app():
    await application.initialize()
    await application.start()
    if WEBHOOK_BASE:
        url = f"{WEBHOOK_BASE}/{BOT_TOKEN}"
        try:
            await application.bot.set_webhook(url=url, drop_pending_updates=True)
            logger.info("Webhook registered: %s", url)
        except Exception as exc:  # noqa: BLE001
            logger.error("set_webhook failed: %s", exc)


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.create_task(_init_app())
thread = threading.Thread(target=loop.run_forever, daemon=True)
thread.start()


@app.route(f"/{BOT_TOKEN}", methods=["POST"])
@app.route("/", methods=["POST"])
def webhook():
    if request.method == "POST":
        try:
            update = Update.de_json(request.get_json(force=True), application.bot)
            loop.call_soon_threadsafe(asyncio.create_task, application.process_update(update))
            return Response("ok", status=200)
        except Exception as exc:
            logger.error("Webhook error: %s", exc)
            return Response("error", status=500)
    return Response("ok", status=200)


@app.route("/healthz", methods=["GET"])
def healthz():
    return Response("ok", status=200)


@app.route("/debug/config", methods=["GET"])
def debug_config():
    return Response(
        json.dumps(config.get("chat_configs", {}), ensure_ascii=False),
        mimetype="application/json",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
