import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

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
    print("------ NEW MESSAGE ------")
    print(msg)
    if msg.text:
        print("Text:", msg.text)

    elif msg.photo:
        print("Photo received")
        photo = msg.photo[-1]  # highest resolution
        file = await context.bot.get_file(photo.file_id)
        path = os.path.join(DOWNLOAD_DIR, f"{photo.file_id}.jpg")
        await file.download_to_drive(path)
        print("Saved to:", path)

    elif msg.video:
        print("Video received")
        video = msg.video
        file = await context.bot.get_file(video.file_id)
        path = os.path.join(DOWNLOAD_DIR, f"{video.file_id}.mp4")
        await file.download_to_drive(path)
        print("Saved to:", path)

    elif msg.audio:
        print("Audio received")
        audio = msg.audio
        file = await context.bot.get_file(audio.file_id)
        path = os.path.join(DOWNLOAD_DIR, f"{audio.file_id}.mp3")
        await file.download_to_drive(path)
        print("Saved to:", path)

    elif msg.document:
        print("Document received")
        doc = msg.document
        file = await context.bot.get_file(doc.file_id)
        path = os.path.join(DOWNLOAD_DIR, doc.file_name)
        await file.download_to_drive(path)
        print("Saved to:", path)

    else:
        print("Other message type received")


# Create the application (bot)
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.ALL, handle_message))
