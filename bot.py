import os
import logging
import asyncio
import httpx
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import NetworkError, TimedOut, BadRequest

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
    {"tag": "@milanorossonerareplay", "name": "Milanorossonerareplay"},
    # Aggiungi altri canali se necessario
]
CONTENT = os.getenv("REWARD_LINK", "Contenuto sbloccato: https://example.com/default")

# Crea l'applicazione Telegram con timeout
application = Application.builder().token(TOKEN).http_timeout(10).build()

# Inizializza l'applicazione
async def init_application():
    try:
        await application.initialize()
        logger.info("Application inizializzata correttamente")
    except Exception as e:
        logger.error(f"Errore durante l'inizializzazione dell'Application: {e}")
        raise

# Handler per gli errori
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Errore durante l'elaborazione dell'aggiornamento {update}: {context.error}")
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Si è verificato un errore durante la verifica. Riprova con /start o attendi qualche secondo."
            )
        except Exception as e:
            logger.error(f"Errore nell'invio del messaggio di errore: {e}")

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
    
    # Prova con retry in caso di errore di rete
    for attempt in range(3):
        try:
            await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            break
        except (NetworkError, TimedOut) as e:
            logger.warning(f"Tentativo {attempt + 1} fallito: {e}")
            if attempt < 2:
                await asyncio.sleep(2)  # Attendi 2 secondi prima di riprovare
            else:
                raise

# Handler per la verifica dell'iscrizione
async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Ricevuta verifica da user_id: {update.callback_query.from_user.id}")
    query = update.callback_query
    user_id = query.from_user.id
    missing = []
    
    for channel in REQUIRED_CHANNELS:
        try:
            # Esegui get_chat_member con timeout
            member = await asyncio.wait_for(
                context.bot.get_chat_member(chat_id=channel["tag"], user_id=user_id),
                timeout=5
            )
            if member.status not in ["member", "administrator", "creator"]:
                missing.append(channel)
        except asyncio.TimeoutError:
            logger.error(f"Timeout durante la verifica del canale {channel['tag']}")
            missing.append(channel)
        except Exception as e:
            logger.error(f"Errore durante la verifica del canale {channel['tag']}: {e}")
            missing.append(channel)
    
    if not missing:
        try:
            await query.message.edit_text(CONTENT)
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Messaggio non modificato, contenuto già corretto")
            else:
                raise
    else:
        keyboard = [
            [InlineKeyboardButton(channel["name"], url=f"https://t.me/{channel['tag'][1:]}")]
            for channel in missing
        ]
        keyboard.append([InlineKeyboardButton("Riprova", callback_data="check")])
        missing_names = [channel["name"] for channel in missing]
        new_text = "Iscriviti a: " + "\n".join(missing_names)
        
        # Controlla se il messaggio è cambiato prima di modificarlo
        try:
            if query.message.text != new_text or query.message.reply_markup != InlineKeyboardMarkup(keyboard):
                await query.message.edit_text(new_text, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                logger.info("Messaggio non modificato, stesso contenuto e markup")
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Messaggio non modificato, contenuto già corretto")
            else:
                raise

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
            # Esegui process_update con timeout
            await asyncio.wait_for(application.process_update(update), timeout=10)
        else:
            logger.warning("Nessun aggiornamento valido ricevuto")
        return "OK"
    except asyncio.TimeoutError:
        logger.error("Timeout durante l'elaborazione dell'aggiornamento")
        return "OK"
    except Exception as e:
        logger.error(f"Errore nel processare l'aggiornamento: {e}")
        return "OK"

# Endpoint di salute
@app_flask.route("/")
def health():
    logger.info("Richiesta endpoint di salute")
    return "Bot is running"

# Inizializza l'applicazione con un event loop dedicato
try:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_application())
except Exception as e:
    logger.error(f"Errore durante l'inizializzazione dell'Application: {e}")
    raise

# Registra gli handler
try:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(check_subscription, pattern="check"))
    application.add_error_handler(error_handler)
    logger.info("Handler registrati correttamente: /start, check_subscription, error_handler")
except Exception as e:
    logger.error(f"Errore durante la registrazione degli handler: {e}")
    raise

# Gunicorn avvia il server
if __name__ == "__main__":
    logger.info("Bot inizializzato. Server dovrebbe essere avviato da Gunicorn in produzione.")