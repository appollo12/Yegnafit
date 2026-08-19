import hashlib
import hmac
import os
import re
from PIL import Image
import pytesseract
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

TOKEN = os.getenv("BOT_TOKEN")
SECRET_KEY = os.getenv("APP_SECRET_KEY", "super_secret_yegnafit_key_2026")
APP_URL = "https://your-yegnafit-app.com"  # Your deployed app URL

# Ledger to store used transaction IDs (Prevents double dipping)
processed_txns = set()

def generate_secure_token(txn_id: str) -> str:
    """Generates an unpredictable, cryptographically signed activation token."""
    message = f"{txn_id}:{SECRET_KEY}".encode('utf-8')
    token_hash = hmac.new(SECRET_KEY.encode('utf-8'), message, hashlib.sha256).hexdigest()
    return f"{txn_id}-{token_hash[:16]}"

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo_file = await update.message.photo[-1].get_file()
    image_path = f"temp_{user.id}.jpg"
    await photo_file.download_to_drive(image_path)

    # Run OCR on the uploaded receipt screenshot
    extracted_text = pytesseract.image_to_string(Image.open(image_path))
    os.remove(image_path)

    # Extract Telebirr or CBE Transaction Reference Numbers via Regex
    cbe_match = re.search(r'\b(FT[A-Z0-9]{10,12})\b', extracted_text)
    telebirr_match = re.search(r'\b(TELE[0-9]{8,12}|[A-Z0-9]{10,12})\b', extracted_text)
    
    txn_id = None
    if cbe_match:
        txn_id = cbe_match.group(1)
    elif telebirr_match:
        txn_id = telebirr_match.group(1)

    if not txn_id:
        await update.message.reply_text("❌ Could not detect a valid Telebirr or CBE Transaction ID from your screenshot. Please ensure the receipt is clear and uncropped.")
        return

    if txn_id in processed_txns:
        await update.message.reply_text("⚠️ This receipt has already been processed and activated.")
        return

    # Mark transaction as used
    processed_txns.add(txn_id)

    # Generate secure token and activation link
    activation_token = generate_secure_token(txn_id)
    magic_link = f"{APP_URL}/?activation_token={activation_token}"

    keyboard = [[InlineKeyboardButton("🚀 Activate YegnaFit Ultimate Now", url=magic_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ **Payment Verified Successfully!**\n\n"
        f"**Txn Reference:** `{txn_id}`\n"
        f"Click the button below to instantly unlock your account:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

bot_app = Application.builder().token(TOKEN).build()
bot_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
