import os
import sys
import uvicorn
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from pyngrok import ngrok
from telegram import Update
from dotenv import load_dotenv

# Add the ingestion directory to path for proper imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from telegram_bot import app as ptb_app
except ImportError:
    # If running as a module, try relative import
    try:
        from .telegram_bot import app as ptb_app
    except ImportError:
         print("Could not import telegram_bot. Ensure it is in the same directory.")
         sys.exit(1)

load_dotenv()

NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
PORT = int(os.getenv("PORT", 8000))
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "my_whatsapp_verify_token")

# Global variables for state
public_url = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Retrieve public URL from global scope
    global public_url
    
    if public_url:
        webhook_url = f"{public_url}/telegram"
        print(f"Setting Telegram webhook to: {webhook_url}")
        await ptb_app.bot.set_webhook(url=webhook_url)
    
    # Initialize and start the Telegram bot application
    async with ptb_app:
        await ptb_app.start()
        yield
        await ptb_app.stop()

# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

@app.post("/telegram")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram updates."""
    try:
        data = await request.json()
        update = Update.de_json(data, ptb_app.bot)
        await ptb_app.process_update(update)
    except Exception as e:
        print(f"Error processing Telegram update: {e}")
    return Response(content="OK", status_code=200)

@app.get("/webhook")
async def whatsapp_verify(request: Request):
    """Handle WhatsApp webhook verification (GET request from Meta)."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
            print("WEBHOOK_VERIFIED")
            # Return the challenge token as plain text
            return Response(content=challenge, media_type="text/plain", status_code=200)
        else:
            return Response(content="Verification failed", status_code=403)
    return Response(content="Hello world", status_code=200)

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    """Handle incoming WhatsApp messages (POST request from Meta)."""
    try:
        data = await request.json()
        print("------ NEW WHATSAPP MESSAGE ------")
        print(data)
        
        # Add your WhatsApp message processing logic here
        
    except Exception as e:
        print(f"Error processing WhatsApp message: {e}")
        
    return Response(content="RECEIVED", status_code=200)

def main():
    global public_url
    
    if not NGROK_AUTH_TOKEN:
        print("Error: NGROK_AUTH_TOKEN not found in .env file")
        sys.exit(1)

    print("Killing any existing ngrok processes...")
    ngrok.kill()
    
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)

    try:
        # Open a HTTP tunnel on the default port
        tunnel = ngrok.connect(PORT, "http")
        public_url = tunnel.public_url
        
        print("=" * 50)
        print(f"Public URL: {public_url}")
        print(f"Telegram Webhook: {public_url}/telegram")
        print(f"WhatsApp Webhook: {public_url}/webhook")
        print("=" * 50)

        # Run the server
        uvicorn.run(app, host="0.0.0.0", port=PORT)
        
    except Exception as e:
        print(f"Failed to start: {e}")
        ngrok.kill()

if __name__ == "__main__":
    main()
