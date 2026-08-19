import hashlib
import hmac
import os
import re
from contextlib import asynccontextmanager
from PIL import Image
import pytesseract
from fastapi import FastAPI
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
SECRET_KEY = os.getenv("APP_SECRET_KEY", "super_secret_yegnafit_key_2026")
APP_URL = os.getenv("APP_URL", "https://your-yegnafit-app.com")

processed_txns = set()

def generate_secure_token(txn_id: str, tier: str = "premium") -> str:
    message = f"{txn_id}:{tier}:{SECRET_KEY}".encode('utf-8')
    token_hash = hmac.new(SECRET_KEY.encode('utf-8'), message, hashlib.sha256).hexdigest()
    return f"{txn_id}-{tier}-{token_hash[:16]}"

# Welcome command handler
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Welcome to YegnaFit Bot!**\n\n"
        "Please upload a photo or document screenshot of your CBE or Telebirr payment receipt to activate your account.",
        parse_mode="Markdown"
    )

# Process incoming receipts (Photos or Document images)
async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    image_path = f"temp_{user.id}.jpg"

    # Handle standard photo OR document upload
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
    elif update.message.document and update.message.document.mime_type.startswith('image/'):
        file = await update.message.document.get_file()
    else:
        await update.message.reply_text("📸 Please send a valid image file of your receipt.")
        return

    await file.download_to_drive(image_path)

    # Extract text using OCR
    try:
        extracted_text = pytesseract.image_to_string(Image.open(image_path))
    except Exception as e:
        await update.message.reply_text("❌ Error processing image OCR. Please try again.")
        return
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

    # Pattern match for CBE and Telebirr
    cbe_match = re.search(r'\b(FT[A-Z0-9]{10,12})\b', extracted_text)
    telebirr_match = re.search(r'\b(TELE[0-9]{8,12}|[A-Z0-9]{10,12})\b', extracted_text)
    
    txn_id = cbe_match.group(1) if cbe_match else (telebirr_match.group(1) if telebirr_match else None)

    if not txn_id:
        await update.message.reply_text("❌ Could not detect a valid Transaction ID. Make sure the screenshot is clear and uncropped.")
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
        f"Click the button below to unlock your subscription:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_app = Application.builder().token(TOKEN).build()
    
    # Handlers for commands and media
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_receipt))
    
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()
    yield
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"status": "YegnaFit Bot Server Running"}
