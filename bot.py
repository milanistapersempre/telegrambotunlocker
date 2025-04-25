import os
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Configura Flask
app_flask = Flask(__name__)

# Configura il token e altre variabili
TOKEN = os.getenv("TELEGRAM_TOKEN")
REQUIRED_CHANNELS = [
    {"tag": "@milanorossonerareplay", "name": "Canale Replay Milan"},    
]  # Sostituisci con i tuoi canali
CONTENT = os.getenv("REWARD_LINK", "Link sbloccato: https://t.me/+Jqgbw-dewP04MTE0")

# Crea l'applicazione Telegram
application = Application.builder().token(TOKEN).build()

# Handler per il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(channel["name"], url=f"https://t.me/{channel['tag'][1:]}")]
        for channel in REQUIRED_CHANNELS
    ]
    keyboard.append([InlineKeyboardButton("Verifica", callback_data="check")])
    await update.message.reply_text("Ciao, iscriviti ai seguenti canali per sbloccare il link:", reply_markup=InlineKeyboardMarkup(keyboard))

# Handler per la verifica dell'iscrizione
async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    missing = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel["tag"], user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                missing.append(channel)
        except:
            missing.append(channel)
    if not missing:
        await query.message.edit_text(CONTENT)
    else:
        keyboard = [
            [InlineKeyboardButton(channel["name"], url=f"https://t.me/{channel['tag'][1:]}")]
            for channel in missing
        ]
        keyboard.append([InlineKeyboardButton("Riprova", callback_data="check")])
        missing_names = [channel["name"] for channel in missing]
        await query.message.edit_text("Iscriviti a: " + "\n".join(missing_names), reply_markup=InlineKeyboardMarkup(keyboard))

# Endpoint Flask per il webhook
@app_flask.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(), application.bot)
    await application.process_update(update)
    return "OK"

# Endpoint di salute
@app_flask.route("/")
def health():
    return "Bot is running"

# Inizializza il bot
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(check_subscription, pattern="check"))

# Gunicorn avvia il server, non Flask
if __name__ == "__main__":
    print("Bot initialized. Server should be started by Gunicorn in production.")