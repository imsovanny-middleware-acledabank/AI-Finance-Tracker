#!/usr/bin/env python
"""
Script to help find your Telegram user ID.
Run this script, then message your bot with /start or any text.
Your Telegram ID will be displayed here.
"""

import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not TELEGRAM_BOT_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN not found in .env file")
    print("Please set your bot token first")
    exit(1)

async def handle_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Print user ID and message info."""
    user = update.message.from_user
    print(f"\n{'='*50}")
    print(f"USER ID: {user.id}")
    print(f"First Name: {user.first_name}")
    print(f"Last Name: {user.last_name}")
    print(f"Username: @{user.username}" if user.username else "Username: Not set")
    print(f"Message: {update.message.text}")
    print(f"{'='*50}\n")
    
    await update.message.reply_text(
        f"Your Telegram ID is: `{user.id}`\n\n"
        f"Use this ID on the dashboard at:\n"
        f"http://localhost:8000/?telegram_id={user.id}",
        parse_mode="Markdown"
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.message.from_user
    print(f"\n{'='*50}")
    print(f"NEW USER STARTED BOT")
    print(f"USER ID: {user.id}")
    print(f"Name: {user.first_name}")
    print(f"{'='*50}\n")
    
    await update.message.reply_text(
        f"Hello {user.first_name}! 👋\n\n"
        f"Your Telegram ID: `{user.id}`\n\n"
        f"View your financial data on the dashboard:\n"
        f"http://localhost:8000/?telegram_id={user.id}",
        parse_mode="Markdown"
    )

def main():
    print("\n🔍 Telegram ID Finder")
    print("="*50)
    print("Start your bot and send any message...")
    print("Your Telegram ID will be shown here")
    print("="*50 + "\n")
    
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT, handle_any_message))
    
    print("Bot is running... Send a message to your bot to get your ID")
    print("Press Ctrl+C to stop\n")
    
    app.run_polling()

if __name__ == '__main__':
    main()
