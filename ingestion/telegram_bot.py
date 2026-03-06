import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from IPython.display import display, Image, Audio, Video

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

# Ensure downloads directory exists
os.makedirs("downloads", exist_ok=True)


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
        path = f"downloads/{photo.file_id}.jpg"
        await file.download_to_drive(path)
        display(Image(filename=path))

    elif msg.video:
        print("Video received")
        video = msg.video
        file = await context.bot.get_file(video.file_id)
        path = f"downloads/{video.file_id}.mp4"
        await file.download_to_drive(path)
        display(Video(filename=path, embed=True))

    elif msg.audio:
        print("Audio received")
        audio = msg.audio
        file = await context.bot.get_file(audio.file_id)
        path = f"downloads/{audio.file_id}.mp3"
        await file.download_to_drive(path)
        display(Audio(filename=path))

    elif msg.document:
        print("Document received")
        doc = msg.document
        file = await context.bot.get_file(doc.file_id)
        path = f"downloads/{doc.file_name}"
        await file.download_to_drive(path)
        print("Saved to:", path)

    else:
        print("Other message type received")


# Create the application (bot)
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.ALL, handle_message))
