# tracker/management/commands/run_bot.py
import os
import asyncio
from decimal import Decimal, InvalidOperation
from datetime import date as _date, datetime
from django.core.management.base import BaseCommand
from django.db.models import Sum
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from tracker.services import analyze_finance_text
from tracker.models import Transaction
from dotenv import load_dotenv

load_dotenv()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process text, voice, photos, and documents for financial transactions."""
    if not update.message:
        return
    
    user_input = None
    user_id = update.message.from_user.id
    
    # Extract text from different message types
    if update.message.text:
        user_input = update.message.text
    elif update.message.voice:
        # Voice message: download and transcribe
        try:
            await update.message.reply_text("🎤 Processing voice message...")
            
            # Download voice file
            voice_file = await context.bot.get_file(update.message.voice.file_id)
            voice_path = f"/tmp/voice_{user_id}_{update.message.voice.file_unique_id}.ogg"
            await voice_file.download_to_drive(voice_path)
            
            # Try to transcribe using speech_recognition
            def transcribe_voice(filepath):
                try:
                    import speech_recognition as sr
                    from pydub import AudioSegment
                    
                    # Convert OGG to WAV
                    audio = AudioSegment.from_ogg(filepath)
                    wav_path = filepath.replace('.ogg', '.wav')
                    audio.export(wav_path, format="wav")
                    
                    # Transcribe
                    recognizer = sr.Recognizer()
                    with sr.AudioFile(wav_path) as source:
                        audio_data = recognizer.record(source)
                    
                    text = recognizer.recognize_google(audio_data)
                    return text
                except ImportError:
                    return None
                except Exception as e:
                    raise ValueError(f"Transcription failed: {str(e)}")
            
            user_input = await asyncio.to_thread(transcribe_voice, voice_path)
            
            if not user_input:
                await update.message.reply_text(
                    "🎤 Voice transcription requires: `pip install SpeechRecognition pydub`\n"
                    "For now, please send your transaction as text (e.g., 'spent $10 on food')."
                )
                return
        except Exception as e:
            await update.message.reply_text(f"❌ Voice processing error: {str(e)}")
            return
    elif update.message.photo:
        # Photo: use caption if available
        if update.message.caption:
            user_input = update.message.caption
        else:
            await update.message.reply_text("📷 Photo received. Please include a caption (e.g., 'spent $5 on lunch').")
            return
    elif update.message.document:
        # Document: use caption if available
        if update.message.caption:
            user_input = update.message.caption
        else:
            await update.message.reply_text("📄 Document received. Please include a caption (e.g., 'spent $5 on lunch').")
            return
    else:
        # Unsupported message type
        await update.message.reply_text(
            "ℹ️ I process text messages, photos/documents with captions, and voice messages.\n"
            "Send a message like: 'spent $5 on lunch' or reply to media with this caption."
        )
        return
    
    if not user_input:
        return

    try:
        # 1. AI Detects entries (run in thread to avoid blocking asyncio loop)
        data = await asyncio.to_thread(analyze_finance_text, user_input)

        if not isinstance(data, dict):
            raise ValueError("AI response was not a JSON object")

        # Check if this is a non-transaction query
        if not data.get('is_transaction', True):
            response = f"ℹ️ {data.get('message', 'This does not appear to be a financial transaction.')}"
            await update.message.reply_text(response)
            return

        # Validate required fields
        if not data.get('amount'):
            raise ValueError("Parsed data missing required field: amount")
        if not data.get('category'):
            raise ValueError("Parsed data missing required field: category")
        if not data.get('type'):
            raise ValueError("Parsed data missing required field: type")

        # Parse amount into Decimal (allow strings like "$1,234.56")
        def parse_amount(value):
            if isinstance(value, (int, float, Decimal)):
                return Decimal(str(value))
            if isinstance(value, str):
                # remove currency symbols and commas
                cleaned = value.replace('$', '').replace(',', '').strip()
                return Decimal(cleaned)
            raise InvalidOperation("unsupported amount type")

        try:
            amount_dec = parse_amount(data['amount'])
        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"Could not parse amount: {e}")

        # Parse date if provided, else use today
        def parse_date(value):
            if not value:
                return _date.today()
            if isinstance(value, _date):
                return value
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, str):
                try:
                    return _date.fromisoformat(value)
                except Exception:
                    # try common formats
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                        try:
                            return datetime.strptime(value, fmt).date()
                        except Exception:
                            continue
            raise ValueError("Unsupported date format")

        try:
            tx_date = parse_date(data.get('date'))
        except ValueError:
            # fallback to today if parsing fails
            tx_date = _date.today()

        tx_type = str(data.get('type')).lower()
        if tx_type not in ('income', 'expense'):
            raise ValueError("Parsed field 'type' must be 'income' or 'expense'")

        # 2. Save to database automatically (run in thread to avoid async ORM call)
        from tracker.models import Category
        
        # Get or create category
        category_name = data.get('category', 'Other')
        category, _ = await asyncio.to_thread(Category.objects.get_or_create, name=category_name, defaults={'icon': '💰'})
        
        create_kwargs = dict(
            telegram_id=user_id,
            amount=amount_dec,
            category_name=category_name,
            category=category,
            transaction_type=tx_type,
            note=data.get('note'),
            transaction_date=tx_date,
            is_recurring=False,
            tags=''
        )
        await asyncio.to_thread(Transaction.objects.create, **create_kwargs)

        # 3. Success Feedback [cite: 16]
        response = (
            f"✅ *Recorded {tx_type}*\n"
            f"💰 Amount: ${amount_dec:.2f}\n"
            f"📂 Category: {category.icon} {category_name}\n"
            f"📝 Note: {data.get('note', 'N/A')}"
        )
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await update.message.reply_text(f"❌ Error processing request: {str(e)}")

async def cmd_total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show total expenses and income."""
    user_id = update.message.from_user.id
    
    def fetch_totals():
        expenses = Transaction.objects.filter(telegram_id=user_id, transaction_type='expense').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        income = Transaction.objects.filter(telegram_id=user_id, transaction_type='income').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        return expenses, income
    
    expenses, income = await asyncio.to_thread(fetch_totals)
    response = (
        f"💰 *Financial Summary*\n"
        f"💸 Total Expenses: ${expenses:.2f}\n"
        f"💵 Total Income: ${income:.2f}\n"
        f"📊 Net: ${(income - expenses):.2f}"
    )
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

async def cmd_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show total expenses."""
    user_id = update.message.from_user.id
    
    def fetch_expenses():
        total = Transaction.objects.filter(telegram_id=user_id, transaction_type='expense').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        count = Transaction.objects.filter(telegram_id=user_id, transaction_type='expense').count()
        return total, count
    
    total, count = await asyncio.to_thread(fetch_expenses)
    response = f"💸 Total Expenses: ${total:.2f} ({count} transactions)"
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

async def cmd_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show total income."""
    user_id = update.message.from_user.id
    
    def fetch_income():
        total = Transaction.objects.filter(telegram_id=user_id, transaction_type='income').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        count = Transaction.objects.filter(telegram_id=user_id, transaction_type='income').count()
        return total, count
    
    total, count = await asyncio.to_thread(fetch_income)
    response = f"💵 Total Income: ${total:.2f} ({count} transactions)"
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent transactions."""
    user_id = update.message.from_user.id
    
    def fetch_list():
        return list(Transaction.objects.filter(telegram_id=user_id).order_by('-transaction_date')[:10])
    
    transactions = await asyncio.to_thread(fetch_list)
    if not transactions:
        await update.message.reply_text("📋 No transactions recorded yet.")
        return
    
    lines = ["📋 *Recent Transactions (last 10):*"]
    for tx in transactions:
        icon = "💸" if tx.transaction_type == 'expense' else "💵"
        lines.append(f"{icon} {tx.transaction_date}: ${tx.amount} ({tx.category_name or tx.category}) - {tx.note or 'N/A'}")
    
    response = "\n".join(lines)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show start message with dashboard link."""
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name or "User"
    
    response = (
        f"👋 Hello {user_name}!\n\n"
        f"💰 Welcome to *AI Finance Bot*\n\n"
        f"Your Telegram ID: `{user_id}`\n\n"
        f"📊 *View your dashboard:*\n"
        f"http://localhost:8000/?telegram_id={user_id}\n\n"
        f"📝 *How to use:*\n"
        f"• Send: 'spent $50 on food'\n"
        f"• Send: 'earned $1000 salary'\n"
        f"• Send voice messages with transactions\n"
        f"• Use /total, /expenses, /income, /list commands\n\n"
        f"✨ Your transactions sync instantly to the dashboard!"
    )
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

class Command(BaseCommand):
    help = "Runs the Telegram bot"

    def handle(self, *args, **options):
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            self.stdout.write(self.style.ERROR("TELEGRAM_BOT_TOKEN not found in .env"))
            return

        self.stdout.write(self.style.SUCCESS("Bot is starting..."))
        app = ApplicationBuilder().token(token).build()
        
        # Add command handlers
        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("total", cmd_total))
        app.add_handler(CommandHandler("expenses", cmd_expenses))
        app.add_handler(CommandHandler("income", cmd_income))
        app.add_handler(CommandHandler("list", cmd_list))
        
        # Add message handler for text messages
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        app.run_polling()