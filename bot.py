import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Configura il logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configura Flask
app_flask = Flask(__name__)

# Configura il token e altre variabili
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    logger.error("TELEGRAM_TOKEN non trovato nelle variabili d'ambiente")
    raise ValueError("TELEGRAM_TOKEN non trovato")
REQUIRED_CHANNELS = [
    {"tag": "@milanorossonerareplay", "name": "Canale 1"},
    # Aggiungi altri canali se necessario
]
CONTENT = os.getenv("REWARD_LINK", "Contenuto sbloccato: https://t.me/+RFashWjj1q9mMTFk")

# Crea l'applicazione Telegram
application = Application.builder().token(TOKEN).build()

# Inizializza l'applicazione
async def init_application():
    try:
        await application.initialize()
        logger.info("Application inizializzata correttamente")
    except Exception as e:
        logger.error(f"Errore durante l'inizializzazione dell'Application: {e}")
        raise

# Handler per il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    logger.info(f"Ricevuto comando /start da user_id: {update.effective_user.id}, nome: {user_name}")
    keyboard = [
        [InlineKeyboardButton(channel["name"], url=f"https://t.me/{channel['tag'][1:]}")]
        for channel in REQUIRED_CHANNELS
    ]
    keyboard.append([InlineKeyboardButton("Verifica", callback_data="check")])
    
    # Messaggio formattato con Markdown
    message = (
        f"Ciao {user_name}! Iscriviti ai canali qui sotto per sbloccare il link.\n"
        "__Il link potrebbe arrivare con un ritardo di circa 1 minuto.__\n"
        "*Il bot a volte potrebbe laggare, quindi se non vi appare subito l'elenco dei canali a cui dovete iscriverti, "
        "oppure se la verifica dell'iscrizione non viene effettuata correttamente, riprovate scrivendo /start. "
        "Se continua a laggare, aspettate qualche secondo e riprovate.*"
    )
    
    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# Handler per la verifica dell'iscrizione
async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Ricevuta verifica da user_id: {update.callback_query.from_user.id}")
    query = update.callback_query
    user_id = query.from_user.id
    missing = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel["tag"], user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                missing.append(channel)
        except Exception as e:
            logger.error(f"Errore durante la verifica del canale {channel['tag']}: {e}")
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
    try:
        logger.info("Ricevuta richiesta POST al webhook")
        update_data = request.get_json()
        logger.info(f"Dati ricevuti: {update_data}")
        update = Update.de_json(update_data, application.bot)
        if update:
            logger.info(f"Aggiornamento ricevuto: update_id={update.update_id}")
            # Esegui process_update in modo asincrono
            await application.process_update(update)
        else:
            logger.warning("Nessun aggiornamento valido ricevuto")
        return "OK"
    except Exception as e:
        logger.error(f"Errore nel processare l'aggiornamento: {e}")
        return "OK"

# Endpoint di salute
@app_flask.route("/")
def health():
    logger.info("Richiesta endpoint di salute")
    return "Bot is running"

# Inizializza l'applicazione
loop = asyncio.get_event_loop()
loop.run_until_complete(init_application())

# Registra gli handler
try:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(check_subscription, pattern="check"))
    logger.info("Handler registrati correttamente: /start, check_subscription")
except Exception as e:
    logger.error(f"Errore durante la registrazione degli handler: {e}")
    raise

# Gunicorn avvia il server
if __name__ == "__main__":
    logger.info("Bot inizializzato. Server dovrebbe essere avviato da Gunicorn in produzione.")