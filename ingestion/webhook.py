import os
import sys
from pathlib import Path

# Add the ingestion directory to path for proper imports
sys.path.insert(0, str(Path(__file__).parent))

from telegram_bot import app
from pyngrok import ngrok
from dotenv import load_dotenv

load_dotenv()

NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
PORT = int(os.getenv("PORT", 8000))

if not NGROK_AUTH_TOKEN:
    print("Error: NGROK_AUTH_TOKEN not found in .env file")
    sys.exit(1)

ngrok.set_auth_token(NGROK_AUTH_TOKEN)

tunnel = ngrok.connect(PORT, "http")
public_url = tunnel.public_url
print("=" * 50)
print(f"Public URL: {public_url}")
print(f"Webhook URL: {public_url}/webhook")
print("=" * 50)

app.run_webhook(
    listen="0.0.0.0",
    port=PORT,
    webhook_url=f"{public_url}/webhook",
    url_path="webhook"
)
