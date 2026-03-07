import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from converters import telegram_to_canonical
from kafkasend import send_to_kafka

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    print("Error: TELEGRAM_TOKEN not found in .env file")
    import sys
    sys.exit(1)

# Ensure downloads directory exists (relative to the script location)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(SCRIPT_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    msg = update.message
    print("------ NEW TELEGRAM MESSAGE ------")
    print(msg)
    
    # Convert to canonical event
    canonical_event = telegram_to_canonical(update)
    
    if canonical_event:
        print("\n------ CANONICAL EVENT ------")
        print(canonical_event.model_dump_json(indent=2))
        
        # Handle media downloads if needed
        if msg.photo:
            photo = msg.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            path = os.path.join(DOWNLOAD_DIR, f"{photo.file_id}.jpg")
            await file.download_to_drive(path)
            print(f"Photo saved to: {path}")
        
        elif msg.video:
            file = await context.bot.get_file(msg.video.file_id)
            path = os.path.join(DOWNLOAD_DIR, f"{msg.video.file_id}.mp4")
            await file.download_to_drive(path)
            print(f"Video saved to: {path}")
        
        elif msg.audio:
            file = await context.bot.get_file(msg.audio.file_id)
            path = os.path.join(DOWNLOAD_DIR, f"{msg.audio.file_id}.mp3")
            await file.download_to_drive(path)
            print(f"Audio saved to: {path}")
        
        elif msg.document:
            file = await context.bot.get_file(msg.document.file_id)
            path = os.path.join(DOWNLOAD_DIR, msg.document.file_name)
            await file.download_to_drive(path)
            print(f"Document saved to: {path}")
        sendsuccessful = send_to_kafka(canonical_event)
        if sendsuccessful:
            print("succesful sending kafka")
        else :
            print("failed to send to kafka")
        
    else:
        print("Could not convert to canonical event")


# Create the application (bot)
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.ALL, handle_message))
