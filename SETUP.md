# Telegram Bot Setup - Local Environment

## Prerequisites
- Python 3.7+
- Telegram Bot Token
- Ngrok Account

## Installation

1. **Create and activate virtual environment** (recommended):
   ```bash
   python -m venv myenv
   myenv\Scripts\activate  # Windows
   # or
   source myenv/bin/activate  # Linux/Mac
   ```

2. **Install required packages**:
   ```bash
   pip install python-telegram-bot pyngrok python-dotenv
   ```

## Configuration

1. **Create a `.env` file** in the `chatters` folder:
   ```bash
   cd chatters
   copy .env.example .env  # Windows
   # or
   cp .env.example .env  # Linux/Mac
   ```

2. **Edit `.env` file** with your credentials:
   ```env
   TELEGRAM_TOKEN=your_actual_bot_token
   NGROK_AUTH_TOKEN=your_actual_ngrok_token
   PORT=8000
   ```

   - Get Telegram token from [@BotFather](https://t.me/BotFather)
   - Get Ngrok token from [ngrok dashboard](https://dashboard.ngrok.com/get-started/your-authtoken)

## Running the Bot

From the `chatters` folder, run:
```bash
cd ingestion
python webhook.py
```

You should see output like:
```
==================================================
Public URL: https://xxxx-xx-xx-xxx-xxx.ngrok.io
Webhook URL: https://xxxx-xx-xx-xxx-xxx.ngrok.io/webhook
==================================================
```

## Features

The bot handles:
- Text messages
- Photos (saved as .jpg)
- Videos (saved as .mp4)
- Audio (saved as .mp3)
- Documents

All files are saved to `chatters/ingestion/downloads/`

## Troubleshooting

- **ModuleNotFoundError**: Make sure all packages are installed
- **TELEGRAM_TOKEN not found**: Check your `.env` file exists and has correct values
- **Connection errors**: Verify your ngrok token is valid
