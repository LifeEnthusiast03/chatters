import os
import sys
import uvicorn
from contextlib import asynccontextmanager
from pathlib import Path
from pymodel import CanonicalEvent, Sender, Content, MediaItem
from converters import whatsapp_to_canonical
from fastapi import FastAPI, Request, Response
from pyngrok import ngrok
from telegram import Update
from dotenv import load_dotenv

# Slack integration
from slack_bolt import App as SlackApp
from slack_bolt.adapter.fastapi import SlackRequestHandler

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
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "sayandutta")

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# Initialize Slack app
slack_app = None
slack_handler = None

# Check if tokens are set and distinct from placeholders
if SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET and SLACK_BOT_TOKEN != "xoxb-your-token":
    # Initialize the Slack Bolt App
    slack_app = SlackApp(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
    slack_handler = SlackRequestHandler(slack_app)
    
    # Event listener for messages
    @slack_app.event("message")
    def handle_message_events(body, logger):
        print("------ NEW SLACK MESSAGE ------")
        print(body)
else:
    print("Warning: SLACK_BOT_TOKEN or SLACK_SIGNING_SECRET not set (or is default). Slack integration disabled.")

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

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    """Handle incoming WhatsApp messages (POST request from Meta)."""
    try:
        data = await request.json()
        print("------ NEW WHATSAPP MESSAGE ------")
        print(data)
        
        # Convert to canonical event
        canonical_event = whatsapp_to_canonical(data)
        
        if canonical_event:
            print("\n------ CANONICAL EVENT ------")
            print(canonical_event.model_dump_json(indent=2))
            
            # TODO: Send canonical_event to your processing pipeline
            # e.g., await send_to_queue(canonical_event)
        else:
            print("Could not convert WhatsApp message to canonical event")
        
    except Exception as e:
        print(f"Error processing WhatsApp message: {e}")
        import traceback
        traceback.print_exc()
        
    return Response(content="RECEIVED", status_code=200)

@app.post("/slack/events")
async def slack_events(req: Request):
    """Handle incoming Slack events."""
    # Debug: Print incoming raw body to verify connectivity
    try:
        raw_body = await req.body()
        print(f"DEBUG: Active connection, body size: {len(raw_body)}")
        # We must re-create the request stream so Bolt can read it again, 
        # or rely on Bolt wrapper which handles this (SlackRequestHandler uses raw body).
        # Actually, reading the body consumes the stream. Bolt's FastAPI adapter handles this carefully,
        # but if WE read it, we might break Bolt if not careful.
        # Let's NOT read the body here unless we are careful.
        # Instead just print headers or something safe.
        print("DEBUG: Active connection")
    except Exception as e:
        print(f"DEBUG: Error reading request: {e}")

    # If the Bolt handler is active, delegate to it
    if slack_handler:
        return await slack_handler.handle(req)
    
    # Fallback: Handle URL verification even if Slack App is not fully configured
    # This allows you to 'Verify' the URL in Slack dashboard before setting up valid tokens
    try:
        body = await req.json()
        if body.get("type") == "url_verification":
            return Response(content=body.get("challenge"), media_type="text/plain", status_code=200)
    except Exception:
        pass
        
    return Response(content="Slack integration not configured", status_code=501)

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
        
        if slack_app:
            print(f"Slack Events URL: {public_url}/slack/events")
        else:
             print("Slack integration disabled (check .env for valid tokens)")
             
        print("=" * 50)

        # Run the server
        uvicorn.run(app, host="0.0.0.0", port=PORT)
        
    except Exception as e:
        print(f"Failed to start: {e}")
        ngrok.kill()

if __name__ == "__main__":
    main()
