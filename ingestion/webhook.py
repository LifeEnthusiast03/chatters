import nest_asyncio
nest_asyncio.apply()

import os
import sys

# Try to import 'app' from 'telegram_bot' in the same directory.
# If we run this script directly, we can just import telegram_bot.
try:
    from telegram_bot import app
except ImportError:
    # If running as a module 'ingestion.webhook', try relative import
    try:
        from .telegram_bot import app
    except ImportError:
        # If running from root as 'python ingestion/webhook.py', try appending path
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from telegram_bot import app

from pyngrok import ngrok
from dotenv import load_dotenv

load_dotenv()

NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
PORT = int(os.getenv("PORT", 8000))

ngrok.set_auth_token(NGROK_AUTH_TOKEN)

tunnel = ngrok.connect(PORT, "http")
public_url = tunnel.public_url
print("Public URL:", public_url)

app.run_webhook(
    listen="0.0.0.0",
    port=PORT,
    webhook_url=f"{public_url}/webhook",
    url_path="webhook"
)
