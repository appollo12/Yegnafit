import hashlib
import hmac
import os
import re
from contextlib import asynccontextmanager
from PIL import Image
import pytesseract
from fastapi import FastAPI
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

TOKEN = os.getenv("BOT_TOKEN")
SECRET_KEY = os.getenv("APP_SECRET_KEY", "super_secret_yegnafit_key_2026")
APP_URL = os.getenv("APP_URL", "https://your-yegnafit-app.com")

processed_txns = set()

def generate_secure_token(txn_id: str, tier: str = "premium") -> str:
    message = f"{txn_id}:{tier}:{SECRET_KEY}".encode('utf-8')
    token_hash = hmac.new(SECRET_KEY.encode('utf-8'), message, hashlib.sha256).hexdigest()
    return f"{txn_id}-{tier}-{token_hash[:16]}"

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo_file = await update.message.photo[-1].get_file()
    image_path = f"temp_{user.id}.jpg"
    await photo_file.download_to_drive(image_path)

    extracted_text = pytesseract.image_to_string(Image.open(image_path))
    if os.path.exists(image_path):
        os.remove(image_path)

    cbe_match = re.search(r'\b(FT[A-Z0-9]{10,12})\b', extracted_text)
    telebirr_match = re.search(r'\b(TELE[0-9]{8,12}|[A-Z0-9]{10,12})\b', extracted_text)
    
    txn_id = cbe_match.group(1) if cbe_match else (telebirr_match.group(1) if telebirr_match else None)

    if not txn_id:
        await update.message.reply_text("❌ Could not detect a valid Telebirr or CBE Transaction ID from your screenshot.")
        return

    if txn_id in processed_txns:
        await update.message.reply_text("⚠️ This receipt has already been processed and activated.")
        return

    processed_txns.add(txn_id)

    activation_token = generate_secure_token(txn_id)
    magic_link = f"{APP_URL}/?activation_token={activation_token}"

    keyboard = [[InlineKeyboardButton("🚀 Activate YegnaFit Ultimate Now", url=magic_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ **Payment Verified Successfully!**\n\n"
        f"**Txn Reference:** `{txn_id}`\n\n"
        f"Click the button below to instantly unlock your account:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# Lifespan runs Telegram bot in parallel with FastAPI web server
@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()
    yield
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()

# FastAPI instance for Uvicorn and Render Health Checks
app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"status": "YegnaFit Bot Server Running"}
