import os
import re
import asyncio
import hashlib
import hmac
from contextlib import asynccontextmanager
from PIL import Image
import pytesseract
from fastapi import FastAPI
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
SECRET_KEY = os.getenv("APP_SECRET_KEY", "super_secret_yegnafit_key_2026")
APP_URL = os.getenv("APP_URL", "https://yegnafitd.onrender.com")

processed_txns = set()

def generate_secure_token(txn_id: str, tier: str = "premium") -> str:
    message = f"{txn_id}:{tier}:{SECRET_KEY}".encode('utf-8')
    token_hash = hmac.new(SECRET_KEY.encode('utf-8'), message, hashlib.sha256).hexdigest()
    return f"{txn_id}-{tier}-{token_hash[:16]}"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Welcome to YegnaFit Bot!**\n\n"
        "Please send a photo of your CBE or Telebirr receipt to verify your payment and activate your subscription.",
        parse_mode="Markdown"
    )

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    image_path = f"temp_{user.id}.jpg"

    if update.message.photo:
        file = await update.message.photo[-1].get_file()
    elif update.message.document and update.message.document.mime_type.startswith('image/'):
        file = await update.message.document.get_file()
    else:
        await update.message.reply_text("📸 Please send a valid image file of your receipt.")
        return

    await file.download_to_drive(image_path)

    try:
        extracted_text = pytesseract.image_to_string(Image.open(image_path))
    except Exception as e:
        await update.message.reply_text("❌ Error processing OCR. Please ensure the image is clear.")
        return
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

    cbe_match = re.search(r'\b(FT[A-Z0-9]{10,12})\b', extracted_text)
    telebirr_match = re.search(r'\b(TELE[0-9]{8,12}|[A-Z0-9]{10,12})\b', extracted_text)
    
    txn_id = cbe_match.group(1) if cbe_match else (telebirr_match.group(1) if telebirr_match else None)

    if not txn_id:
        await update.message.reply_text("❌ Could not detect a valid Transaction ID. Please send an uncropped screenshot.")
        return

    if txn_id in processed_txns:
        await update.message.reply_text("⚠️ This transaction ID has already been activated.")
        return

    processed_txns.add(txn_id)

    activation_token = generate_secure_token(txn_id, tier="premium")
    magic_link = f"{APP_URL}/?activation_token={activation_token}"

    keyboard = [[InlineKeyboardButton("🚀 Activate YegnaFit Now", url=magic_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ **Payment Verified!**\n\n"
        f"**Txn ID:** `{txn_id}`\n\n"
        f"Tap the button below to complete your activation:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

app = FastAPI()

# Global Telegram Application Reference
bot_app = None

@app.on_event("startup")
async def start_telegram_bot():
    global bot_app
    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_receipt))
    
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling(drop_pending_updates=True)

@app.on_event("shutdown")
async def stop_telegram_bot():
    global bot_app
    if bot_app:
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()

@app.get("/")
def read_root():
    return {"status": "YegnaFit Bot Server Active"}
