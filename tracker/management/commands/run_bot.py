# tracker/management/commands/run_bot.py
import os
import asyncio
from decimal import Decimal, InvalidOperation
from datetime import date as _date, datetime
from django.core.management.base import BaseCommand
from django.db.models import Sum
from telegram import Update
from telegram.constants import ParseMode, ChatAction
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from tracker.services import analyze_finance_text, analyze_reply_action
from tracker.models import Transaction
from dotenv import load_dotenv

load_dotenv()

import re

async def handle_reply_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reply to a transaction confirmation message — edit or delete via AI."""
    user_id = update.message.from_user.id
    reply_text = update.message.text
    original_msg = update.message.reply_to_message.text or ''

    # Extract transaction ID from original message (e.g., "#123")
    id_match = re.search(r'#(\d+)', original_msg)
    if not id_match:
        await update.message.reply_text("❌ Cannot find transaction ID in the original message.")
        return

    tx_id = int(id_match.group(1))

    # Verify transaction belongs to user
    def get_tx():
        try:
            return Transaction.objects.get(id=tx_id, telegram_id=user_id)
        except Transaction.DoesNotExist:
            return None

    tx = await asyncio.to_thread(get_tx)
    if not tx:
        await update.message.reply_text(f"❌ Transaction #{tx_id} not found or unauthorized.")
        return

    await update.message.reply_text("🤖 Analyzing your request...")

    try:
        # Ask AI what the user wants to do
        action_data = await asyncio.to_thread(analyze_reply_action, reply_text, original_msg)

        if not isinstance(action_data, dict):
            raise ValueError("AI response was not a JSON object")

        action = action_data.get('action', 'unknown')

        if action == 'delete':
            # Delete the transaction
            def delete_tx():
                info = {
                    'amount': float(tx.amount),
                    'category': tx.category_name,
                    'type': tx.transaction_type,
                    'date': tx.transaction_date.isoformat()
                }
                tx.delete()
                return info

            info = await asyncio.to_thread(delete_tx)
            icon = "💸" if info['type'] == 'expense' else "💵"
            response = (
                f"✅ *Transaction #{tx_id} Deleted*\n"
                f"{icon} {info['type'].capitalize()}: ${info['amount']:.2f}\n"
                f"📂 {info['category']} | 📅 {info['date']}"
            )
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

        elif action == 'edit':
            changes = action_data.get('changes', {})
            if not any(v is not None for v in changes.values()):
                await update.message.reply_text("ℹ️ No changes detected. Please specify what to edit.")
                return

            def apply_edits():
                from tracker.models import Category
                updated_fields = []

                if changes.get('amount') is not None:
                    old = float(tx.amount)
                    new_amt = Decimal(str(changes['amount']))
                    tx.amount = new_amt
                    cur = getattr(tx, 'currency', 'USD') or 'USD'
                    if cur == 'USD':
                        tx.amount_usd = new_amt
                        tx.amount_khr = new_amt * Decimal('4100')
                    else:
                        tx.amount_khr = new_amt
                        tx.amount_usd = new_amt / Decimal('4100')
                    updated_fields.append(f"💰 Amount: ${old:.2f} → ${float(new_amt):.2f}")

                if changes.get('category') is not None:
                    old_cat = tx.category_name
                    new_cat = changes['category']
                    try:
                        cat_obj = Category.objects.get(name__iexact=new_cat)
                    except Category.DoesNotExist:
                        cat_obj, _ = Category.objects.get_or_create(name=new_cat, defaults={'icon': '💰'})
                    tx.category = cat_obj
                    tx.category_name = cat_obj.name
                    updated_fields.append(f"📂 Category: {old_cat} → {cat_obj.name}")

                if changes.get('date') is not None:
                    old_date = tx.transaction_date.isoformat()
                    tx.transaction_date = _date.fromisoformat(changes['date'])
                    updated_fields.append(f"📅 Date: {old_date} → {changes['date']}")

                if changes.get('note') is not None:
                    old_note = tx.note or '(empty)'
                    tx.note = changes['note']
                    updated_fields.append(f"📝 Note: {old_note} → {changes['note']}")

                tx.save()
                return updated_fields

            updated_fields = await asyncio.to_thread(apply_edits)
            lines = '\n'.join(updated_fields)
            response = (
                f"✅ *Transaction #{tx_id} Updated*\n\n"
                f"{lines}"
            )
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

        else:
            msg = action_data.get('message', 'I could not understand your request.')
            await update.message.reply_text(
                f"🤔 {msg}\n\n"
                f"💡 *Tip:* Reply with:\n"
                f"• \"delete\" or \"លុប\" to remove\n"
                f"• \"change amount to 50\" or \"កែតម្លៃ 50\" to edit",
                parse_mode=ParseMode.MARKDOWN
            )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def handle_summary(update: Update, user_id, data):
    """Generate a financial summary report for day/month/year."""
    period = data.get('period', 'month')
    target_date_str = data.get('date')

    try:
        target_date = _date.fromisoformat(target_date_str) if target_date_str else _date.today()
    except (ValueError, TypeError):
        target_date = _date.today()

    def fetch_summary():
        from django.db.models import Sum, Count, Q
        from django.db.models.functions import TruncDate, TruncMonth

        base_qs = Transaction.objects.filter(telegram_id=user_id)

        if period == 'day':
            qs = base_qs.filter(transaction_date=target_date)
            label = f"📅 {target_date.strftime('%d %b %Y')}"
            period_kh = "ប្រចាំថ្ងៃ"
        elif period == 'year':
            qs = base_qs.filter(transaction_date__year=target_date.year)
            label = f"📅 {target_date.year}"
            period_kh = "ប្រចាំឆ្នាំ"
        else:  # month
            qs = base_qs.filter(
                transaction_date__year=target_date.year,
                transaction_date__month=target_date.month
            )
            label = f"📅 {target_date.strftime('%b %Y')}"
            period_kh = "ប្រចាំខែ"

        income_usd = qs.filter(transaction_type='income').aggregate(t=Sum('amount_usd'))['t'] or Decimal('0')
        expense_usd = qs.filter(transaction_type='expense').aggregate(t=Sum('amount_usd'))['t'] or Decimal('0')
        income_count = qs.filter(transaction_type='income').count()
        expense_count = qs.filter(transaction_type='expense').count()
        net = income_usd - expense_usd

        # Top expense categories
        top_cats = (
            qs.filter(transaction_type='expense')
            .values('category_name')
            .annotate(total=Sum('amount_usd'), cnt=Count('id'))
            .order_by('-total')[:5]
        )

        # Daily breakdown for month/year
        daily_data = None
        if period in ('month', 'year'):
            daily_data = list(
                qs.values('transaction_date')
                .annotate(
                    day_income=Sum('amount_usd', filter=Q(transaction_type='income')),
                    day_expense=Sum('amount_usd', filter=Q(transaction_type='expense')),
                )
                .order_by('-transaction_date')[:7]
            )

        return {
            'label': label,
            'period_kh': period_kh,
            'income_usd': income_usd,
            'expense_usd': expense_usd,
            'income_count': income_count,
            'expense_count': expense_count,
            'net': net,
            'top_cats': list(top_cats),
            'daily_data': daily_data,
        }

    s = await asyncio.to_thread(fetch_summary)

    KHR = Decimal('4100')
    net_icon = "🟢" if s['net'] >= 0 else "🔴"
    net_sign = "+" if s['net'] >= 0 else ""

    # Build category lines
    cat_lines = ""
    if s['top_cats']:
        cat_lines = "\n📊 *ចំណាយតាមប្រភេទ / By Category:*\n"
        for i, c in enumerate(s['top_cats'], 1):
            total = c['total'] or Decimal('0')
            cat_lines += f"  {i}. {c['category_name']}: ${total:,.2f} | ៛{total * KHR:,.0f} ({c['cnt']}x)\n"

    # Build daily breakdown
    daily_lines = ""
    if s['daily_data']:
        daily_lines = "\n📆 *ថ្ងៃថ្មីៗ / Recent Days:*\n"
        for d in s['daily_data']:
            day = d['transaction_date']
            d_inc = d['day_income'] or Decimal('0')
            d_exp = d['day_expense'] or Decimal('0')
            d_net = d_inc - d_exp
            d_icon = "🟢" if d_net >= 0 else "🔴"
            daily_lines += f"  {day.strftime('%d %b')}: +${d_inc:,.2f} -${d_exp:,.2f} {d_icon} ${d_net:,.2f}\n"

    response = (
        f"📊 *របាយការណ៍{s['period_kh']} / {s['label']}*\n"
        f"{'━' * 28}\n\n"
        f"💵 *ចំណូល / Income:*\n"
        f"   ${s['income_usd']:,.2f} | ៛{s['income_usd'] * KHR:,.0f}\n"
        f"   📝 {s['income_count']} transactions\n\n"
        f"💸 *ចំណាយ / Expenses:*\n"
        f"   ${s['expense_usd']:,.2f} | ៛{s['expense_usd'] * KHR:,.0f}\n"
        f"   📝 {s['expense_count']} transactions\n\n"
        f"{net_icon} *សមតុល្យ / Net Balance:*\n"
        f"   {net_sign}${s['net']:,.2f} | {net_sign}៛{s['net'] * KHR:,.0f}\n"
        f"{cat_lines}"
        f"{daily_lines}"
    )

    if s['net'] < 0:
        response += f"\n⚠️ *ការព្រមាន:* ចំណាយលើសចំណូល! Expenses exceed income!"

    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


async def handle_balance(update: Update, user_id):
    """Show the user's current balance: total income, total expenses, and remaining."""
    KHR = Decimal('4100')

    def fetch_balance():
        from django.db.models import Sum, Count

        base_qs = Transaction.objects.filter(telegram_id=user_id)

        income_usd = base_qs.filter(transaction_type='income').aggregate(t=Sum('amount_usd'))['t'] or Decimal('0')
        expense_usd = base_qs.filter(transaction_type='expense').aggregate(t=Sum('amount_usd'))['t'] or Decimal('0')
        income_count = base_qs.filter(transaction_type='income').count()
        expense_count = base_qs.filter(transaction_type='expense').count()
        net = income_usd - expense_usd

        # This month
        today = _date.today()
        month_qs = base_qs.filter(
            transaction_date__year=today.year,
            transaction_date__month=today.month
        )
        month_income = month_qs.filter(transaction_type='income').aggregate(t=Sum('amount_usd'))['t'] or Decimal('0')
        month_expense = month_qs.filter(transaction_type='expense').aggregate(t=Sum('amount_usd'))['t'] or Decimal('0')

        # Today
        today_qs = base_qs.filter(transaction_date=today)
        today_income = today_qs.filter(transaction_type='income').aggregate(t=Sum('amount_usd'))['t'] or Decimal('0')
        today_expense = today_qs.filter(transaction_type='expense').aggregate(t=Sum('amount_usd'))['t'] or Decimal('0')

        # Top 3 expense categories
        top_cats = list(
            base_qs.filter(transaction_type='expense')
            .values('category_name')
            .annotate(total=Sum('amount_usd'), cnt=Count('id'))
            .order_by('-total')[:3]
        )

        return {
            'income_usd': income_usd, 'expense_usd': expense_usd,
            'income_count': income_count, 'expense_count': expense_count,
            'net': net,
            'month_income': month_income, 'month_expense': month_expense,
            'today_income': today_income, 'today_expense': today_expense,
            'top_cats': top_cats,
        }

    b = await asyncio.to_thread(fetch_balance)

    net_icon = "🟢" if b['net'] >= 0 else "🔴"
    net_sign = "+" if b['net'] >= 0 else ""
    month_net = b['month_income'] - b['month_expense']
    today_net = b['today_income'] - b['today_expense']

    # Top categories
    cat_lines = ""
    if b['top_cats']:
        cat_lines = "\n📊 *ចំណាយច្រើនបំផុត / Top Expenses:*\n"
        for i, c in enumerate(b['top_cats'], 1):
            total = c['total'] or Decimal('0')
            cat_lines += f"  {i}. {c['category_name']}: ${total:,.2f} | ៛{total * KHR:,.0f}\n"

    response = (
        f"💰 *សមតុល្យគណនី / Account Balance*\n"
        f"{'━' * 28}\n\n"
        f"💵 *ចំណូលសរុប / Total Income:*\n"
        f"   ${b['income_usd']:,.2f} | ៛{b['income_usd'] * KHR:,.0f}\n"
        f"   📝 {b['income_count']} transactions\n\n"
        f"💸 *ចំណាយសរុប / Total Expenses:*\n"
        f"   ${b['expense_usd']:,.2f} | ៛{b['expense_usd'] * KHR:,.0f}\n"
        f"   📝 {b['expense_count']} transactions\n\n"
        f"{net_icon} *នៅសល់ / Remaining:*\n"
        f"   {net_sign}${b['net']:,.2f} | {net_sign}៛{b['net'] * KHR:,.0f}\n\n"
        f"{'━' * 28}\n"
        f"📅 *ខែនេះ / This Month:*\n"
        f"   ↓ ${b['month_income']:,.2f}  ↑ ${b['month_expense']:,.2f}  → ${month_net:,.2f}\n\n"
        f"📆 *ថ្ងៃនេះ / Today:*\n"
        f"   ↓ ${b['today_income']:,.2f}  ↑ ${b['today_expense']:,.2f}  → ${today_net:,.2f}\n"
        f"{cat_lines}"
    )

    if b['net'] < 0:
        deficit = abs(b['net'])
        response += f"\n⚠️ *ការព្រមាន:* ចំណាយលើសចំណូល -${deficit:,.2f} | -៛{deficit * KHR:,.0f}"

    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process text, voice, photos, and documents for financial transactions."""
    if not update.message:
        return
    
    # Check if this is a reply to a bot's transaction confirmation
    if (update.message.reply_to_message
            and update.message.reply_to_message.from_user
            and update.message.reply_to_message.from_user.is_bot
            and update.message.text
            and '✅' in (update.message.reply_to_message.text or '')
            and '#' in (update.message.reply_to_message.text or '')):
        await handle_reply_action(update, context)
        return

    user_input = None
    user_id = update.message.from_user.id
    
    # Extract text from different message types
    if update.message.text:
        user_input = update.message.text
    elif update.message.voice:
        # Voice message: download and send to Gemini for transcription + understanding
        try:
            thinking_msg = await update.message.reply_text("🎤 កំពុងស្តាប់សារសំឡេង... / Processing voice message...")
            await update.message.chat.send_action(ChatAction.TYPING)

            # Download voice file
            voice_file = await context.bot.get_file(update.message.voice.file_id)
            voice_bytes = await voice_file.download_as_bytearray()

            # Use Gemini to transcribe and understand the voice message
            def process_voice_with_gemini(audio_data):
                import google.generativeai as genai
                genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

                candidate_models = [
                    'models/gemini-2.5-flash',
                    'models/gemini-2.0-flash',
                    'models/gemini-2.5-flash-lite',
                ]
                prompt = (
                    "Listen to this voice message and transcribe exactly what the user said. "
                    "Then respond with ONLY the transcribed text, nothing else. "
                    "The user may speak in Khmer (ខ្មែរ) or English. "
                    "If the audio is unclear or too short, respond with: UNCLEAR_AUDIO"
                )
                audio_part = {
                    'mime_type': 'audio/ogg',
                    'data': bytes(audio_data),
                }

                for mname in candidate_models:
                    try:
                        model = genai.GenerativeModel(mname)
                        response = model.generate_content([audio_part, prompt])
                        if response.text:
                            return response.text.strip()
                    except Exception:
                        continue
                return None

            transcribed = await asyncio.to_thread(process_voice_with_gemini, voice_bytes)

            try:
                await thinking_msg.delete()
            except Exception:
                pass

            if not transcribed or transcribed == 'UNCLEAR_AUDIO':
                await update.message.reply_text(
                    "🎤 មិនអាចស្តាប់សារសំឡេងបានច្បាស់។ សូមព្យាយាមម្តងទៀត។\n"
                    "Could not understand the voice message. Please try again."
                )
                return

            user_input = transcribed
            # Show what was transcribed
            await update.message.reply_text(f"🎤 *ស្តាប់បាន / Heard:* {user_input}", parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            await update.message.reply_text(f"❌ Voice processing error: {str(e)}")
            return
    elif update.message.photo:
        # Photo: use Gemini Vision to read the image content
        try:
            thinking_msg = await update.message.reply_text("📷 កំពុងអានរូបភាព... / Reading image...")
            await update.message.chat.send_action(ChatAction.TYPING)

            # Get the largest photo (last in array)
            photo = update.message.photo[-1]
            photo_file = await context.bot.get_file(photo.file_id)
            photo_bytes = await photo_file.download_as_bytearray()

            caption = update.message.caption or ''

            def analyze_photo_with_gemini(img_data, caption_text):
                import google.generativeai as genai
                genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

                candidate_models = [
                    'models/gemini-2.5-flash',
                    'models/gemini-2.0-flash',
                    'models/gemini-2.5-flash-lite',
                ]
                prompt = (
                    "Look at this image carefully. It may be a receipt, invoice, screenshot of a transaction, "
                    "or a photo with text about spending/income.\n\n"
                    "Extract the financial information and respond with ONLY a short text describing the transaction "
                    "in a format like: 'spent $X on [item/category]' or 'income $X from [source]'.\n"
                    "If amounts are in Khmer Riel (៛ or KHR), keep that currency.\n"
                    "If there's Khmer text, translate the meaning but keep numbers as-is.\n"
                    "If the image has no financial information, describe what you see briefly.\n"
                )
                if caption_text:
                    prompt += f"\nUser also wrote this caption: {caption_text}\n"

                image_part = {
                    'mime_type': 'image/jpeg',
                    'data': bytes(img_data),
                }

                for mname in candidate_models:
                    try:
                        model = genai.GenerativeModel(mname)
                        response = model.generate_content([image_part, prompt])
                        if response.text:
                            return response.text.strip()
                    except Exception:
                        continue
                return None

            result = await asyncio.to_thread(analyze_photo_with_gemini, photo_bytes, caption)

            try:
                await thinking_msg.delete()
            except Exception:
                pass

            if not result:
                await update.message.reply_text(
                    "📷 មិនអាចអានរូបភាពបាន។ សូមព្យាយាមម្តងទៀត។\n"
                    "Could not read the image. Please try again."
                )
                return

            user_input = result
            await update.message.reply_text(f"📷 *អានបាន / Read:* {user_input}", parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            await update.message.reply_text(f"❌ Photo processing error: {str(e)}")
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
        # Detect language for thinking message
        def _is_khmer(text):
            khmer_chars = sum(1 for c in text if '\u1780' <= c <= '\u17FF')
            return khmer_chars > len(text) * 0.15

        if _is_khmer(user_input):
            thinking_text = "🤖 កំពុងវិភាគសំណើរបស់អ្នក..."
        else:
            thinking_text = "🤖 Analyzing your request..."

        thinking_msg = await update.message.reply_text(thinking_text)
        await update.message.chat.send_action(ChatAction.TYPING)

        # 1. AI Detects entries (run in thread to avoid blocking asyncio loop)
        data = await asyncio.to_thread(analyze_finance_text, user_input)

        # Delete the "analyzing" message after AI responds
        try:
            await thinking_msg.delete()
        except Exception:
            pass

        if not isinstance(data, dict):
            raise ValueError("AI response was not a JSON object")

        # Check if this is a non-transaction query
        if not data.get('is_transaction', True):
            # Check if it's a summary/report request
            if data.get('is_summary'):
                await handle_summary(update, user_id, data)
                return
            # Check if it's a balance query
            if data.get('is_balance'):
                await handle_balance(update, user_id)
                return
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
        
        # Parse currency info
        currency = data.get('currency', 'USD').upper()
        if currency not in ('USD', 'KHR'):
            currency = 'USD'
        
        amount_usd = None
        amount_khr = None
        try:
            amount_usd = Decimal(str(data.get('amount_usd', 0))) if data.get('amount_usd') else None
            amount_khr = Decimal(str(data.get('amount_khr', 0))) if data.get('amount_khr') else None
        except (InvalidOperation, ValueError):
            pass
        
        # Fallback conversion if AI didn't provide both
        if currency == 'USD' and not amount_khr:
            amount_usd = amount_dec
            amount_khr = amount_dec * Decimal('4100')
        elif currency == 'KHR' and not amount_usd:
            amount_khr = amount_dec
            amount_usd = amount_dec / Decimal('4100')

        create_kwargs = dict(
            telegram_id=user_id,
            amount=amount_dec,
            currency=currency,
            amount_usd=amount_usd,
            amount_khr=amount_khr,
            category_name=category_name,
            category=category,
            transaction_type=tx_type,
            note=data.get('note'),
            transaction_date=tx_date,
            is_recurring=False,
            tags=''
        )
        tx = await asyncio.to_thread(Transaction.objects.create, **create_kwargs)

        # Budget alert check after transaction (expenses only)
        if tx_type == 'expense':
            from tracker.models import Budget
            
            def get_budgets():
                return list(Budget.objects.filter(
                    telegram_id=user_id,
                    category=category,
                    frequency='monthly',
                    is_active=True
                ))
            
            budgets = await asyncio.to_thread(get_budgets)
            for budget in budgets:
                if budget.get_percentage_used() > budget.alert_threshold:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"⚠️ Budget Alert {budget.category.name}: {budget.get_percentage_used():.0f}% (${budget.get_spent_amount():.2f}/{budget.limit_amount:.2f})",
                        parse_mode=ParseMode.MARKDOWN
                    )

        # 3. Success Feedback
        currency_symbol = '$' if currency == 'USD' else '៛'
        response = (
            f"✅ *Recorded {tx_type}* `#{tx.id}`\n"
            f"💰 Amount: {currency_symbol}{amount_dec:,.2f} ({currency})\n"
            f"💱 USD: ${amount_usd:,.2f} | KHR: ៛{amount_khr:,.0f}\n"
            f"📂 Category: {category.icon} {category_name}\n"
            f"📝 Note: {data.get('note', 'N/A')}\n\n"
            f"↩️ _Reply to this message to edit or delete_"
        )
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

        # 4. Available Balance Alert — warn if expenses exceed income
        if tx_type == 'expense':
            def check_balance():
                total_income = Transaction.objects.filter(
                    telegram_id=user_id, transaction_type='income'
                ).aggregate(total=Sum('amount_usd'))['total'] or Decimal('0')
                total_expense = Transaction.objects.filter(
                    telegram_id=user_id, transaction_type='expense'
                ).aggregate(total=Sum('amount_usd'))['total'] or Decimal('0')
                return total_income, total_expense

            total_income, total_expense = await asyncio.to_thread(check_balance)
            net = total_income - total_expense

            if net < 0:
                deficit_usd = abs(net)
                deficit_khr = deficit_usd * Decimal('4100')
                alert = (
                    f"⚠️ *Available Balance Alert*\n\n"
                    f"🔴 Expenses exceed income!\n\n"
                    f"💵 Total Income: ${total_income:,.2f} | ៛{total_income * Decimal('4100'):,.0f}\n"
                    f"💸 Total Expenses: ${total_expense:,.2f} | ៛{total_expense * Decimal('4100'):,.0f}\n"
                    f"📉 Deficit: -${deficit_usd:,.2f} | -៛{deficit_khr:,.0f}\n\n"
                    f"💡 *Tip:* Consider reducing spending or adding income to stay on track."
                )
                await context.bot.send_message(
                    chat_id=user_id,
                    text=alert,
                    parse_mode=ParseMode.MARKDOWN
                )

    except Exception as e:
        err_msg = str(e)
        if 'quota' in err_msg.lower() or 'rate' in err_msg.lower() or '429' in err_msg:
            await update.message.reply_text(
                "⏳ សេវា AI រវល់បណ្តោះអាសន្ន។ សូមព្យាយាមម្តងទៀតក្នុង 1 នាទី។\n"
                "AI service is temporarily busy. Please try again in 1 minute."
            )
        else:
            # Truncate to avoid Telegram 'Message too long' error
            if len(err_msg) > 300:
                err_msg = err_msg[:300] + '...'
            await update.message.reply_text(f"❌ មានបញ្ហា / Error: {err_msg}")

async def cmd_total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show total expenses and income."""
    user_id = update.message.from_user.id
    
    def fetch_totals():
        expenses_usd = Transaction.objects.filter(telegram_id=user_id, transaction_type='expense').aggregate(total=Sum('amount_usd'))['total'] or Decimal('0')
        income_usd = Transaction.objects.filter(telegram_id=user_id, transaction_type='income').aggregate(total=Sum('amount_usd'))['total'] or Decimal('0')
        return expenses_usd, income_usd
    
    expenses_usd, income_usd = await asyncio.to_thread(fetch_totals)
    net_usd = income_usd - expenses_usd
    response = (
        f"💰 *Financial Summary*\n\n"
        f"💸 Total Expenses:\n"
        f"   ${expenses_usd:,.2f} | ៛{expenses_usd * Decimal('4100'):,.0f}\n\n"
        f"💵 Total Income:\n"
        f"   ${income_usd:,.2f} | ៛{income_usd * Decimal('4100'):,.0f}\n\n"
        f"📊 Net:\n"
        f"   ${net_usd:,.2f} | ៛{net_usd * Decimal('4100'):,.0f}"
    )
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

async def cmd_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show total expenses."""
    user_id = update.message.from_user.id
    
    def fetch_expenses():
        total_usd = Transaction.objects.filter(telegram_id=user_id, transaction_type='expense').aggregate(total=Sum('amount_usd'))['total'] or Decimal('0')
        count = Transaction.objects.filter(telegram_id=user_id, transaction_type='expense').count()
        return total_usd, count
    
    total_usd, count = await asyncio.to_thread(fetch_expenses)
    response = f"💸 Total Expenses: ${total_usd:,.2f} | ៛{total_usd * Decimal('4100'):,.0f} ({count} transactions)"
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

async def cmd_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show total income."""
    user_id = update.message.from_user.id
    
    def fetch_income():
        total_usd = Transaction.objects.filter(telegram_id=user_id, transaction_type='income').aggregate(total=Sum('amount_usd'))['total'] or Decimal('0')
        count = Transaction.objects.filter(telegram_id=user_id, transaction_type='income').count()
        return total_usd, count
    
    total_usd, count = await asyncio.to_thread(fetch_income)
    response = f"💵 Total Income: ${total_usd:,.2f} | ៛{total_usd * Decimal('4100'):,.0f} ({count} transactions)"
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
        cur = getattr(tx, 'currency', 'USD') or 'USD'
        sym = '$' if cur == 'USD' else '៛'
        lines.append(f"{icon} {tx.transaction_date}: {sym}{tx.amount:,.2f} ({cur}) - {tx.category_name or tx.category} - {tx.note or 'N/A'}")
    
    response = "\n".join(lines)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show start message with dashboard link."""
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name or "User"
    
    response = (
        f"👋 សួស្តី {user_name}!\n\n"
        f"💰 AI Finance Bot - ជំនួយការហិរញ្ញវត្ថុ\n\n"
        f"🆔 Telegram ID របស់អ្នក:\n"
        f"<code>{user_id}</code>\n"
        f"(ចុចលើលេខដើម្បី copy / Tap to copy)\n\n"
        f"📊 Dashboard:\n"
        f"http://localhost:8000/?telegram_id={user_id}\n\n"
        f"📝 របៀបប្រើ / How to use:\n"
        f"• ផ្ញើ: 'ចំណាយ $5 អាហារ' ឬ 'spent $50 on food'\n"
        f"• ផ្ញើ: 'ចំណូល $1000 ប្រាក់ខែ' ឬ 'earned $1000 salary'\n"
        f"• សួរ: 'តើខែនេះចំណាយប៉ុន្មាន?' ឬ 'monthly summary'\n"
        f"• សួរ: 'នៅសល់ប៉ុន្មាន?' ឬ 'my balance'\n"
        f"• ប្រើ /total, /expenses, /income, /list\n\n"
        f"✨ ប្រតិបត្តិការទាំងអស់ធ្វើសមកាលកម្មទៅ Dashboard ភ្លាមៗ!"
    )
    await update.message.reply_text(response, parse_mode=ParseMode.HTML)


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a transaction by ID. Usage: /delete <transaction_id>"""
    user_id = update.message.from_user.id
    
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /delete <transaction_id>\n"
            "Example: /delete 42\n"
            "Use /list to see transaction IDs"
        )
        return
    
    try:
        transaction_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Transaction ID must be a number")
        return
    
    def delete_tx():
        try:
            tx = Transaction.objects.get(id=transaction_id, telegram_id=user_id)
            tx_info = {
                'id': tx.id,
                'amount': float(tx.amount),
                'category': tx.category_name,
                'date': tx.transaction_date.isoformat(),
                'type': tx.transaction_type
            }
            tx.delete()
            return True, tx_info
        except Transaction.DoesNotExist:
            return False, None
    
    success, tx_info = await asyncio.to_thread(delete_tx)
    
    if success:
        icon = "💸" if tx_info['type'] == 'expense' else "💵"
        response = (
            f"✅ *Transaction Deleted*\n"
            f"{icon} Type: {tx_info['type'].capitalize()}\n"
            f"💰 Amount: ${tx_info['amount']:.2f}\n"
            f"📂 Category: {tx_info['category']}\n"
            f"📅 Date: {tx_info['date']}"
        )
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"❌ Transaction #{transaction_id} not found or unauthorized")

async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit a transaction. Usage: /edit <transaction_id> <field> <value>
    Fields: amount, category, date (YYYY-MM-DD), note"""
    user_id = update.message.from_user.id
    
    if len(context.args) < 3:
        await update.message.reply_text(
            "❌ Usage: /edit <id> <field> <value>\n\n"
            "Fields:\n"
            "• amount - /edit 42 amount 50\n"
            "• category - /edit 42 category Food\n"
            "• date - /edit 42 date 2026-04-19\n"
            "• note - /edit 42 note lunch at cafe\n\n"
            "Use /list to see transaction IDs"
        )
        return
    
    try:
        transaction_id = int(context.args[0])
        field = context.args[1].lower()
        value = ' '.join(context.args[2:])
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Invalid format")
        return
    
    def update_tx():
        from datetime import datetime
        from tracker.models import Category
        
        try:
            tx = Transaction.objects.get(id=transaction_id, telegram_id=user_id)
            old_value = None
            
            if field == 'amount':
                try:
                    old_value = float(tx.amount)
                    tx.amount = float(value)
                except ValueError:
                    return False, None, "Invalid amount"
            
            elif field == 'category':
                try:
                    old_value = tx.category_name
                    category = Category.objects.get(name__iexact=value)
                    tx.category = category
                    tx.category_name = category.name
                except Category.DoesNotExist:
                    return False, None, f"Category '{value}' not found"
            
            elif field == 'date':
                try:
                    old_value = tx.transaction_date.isoformat()
                    tx.transaction_date = datetime.fromisoformat(value).date()
                except (ValueError, AttributeError):
                    return False, None, "Invalid date (use YYYY-MM-DD)"
            
            elif field == 'note':
                old_value = tx.note or "(empty)"
                tx.note = value
            
            else:
                return False, None, f"Field '{field}' not supported"
            
            tx.save()
            return True, (field, old_value, value), None
        except Transaction.DoesNotExist:
            return False, None, "Transaction not found or unauthorized"
    
    success, change_info, error_msg = await asyncio.to_thread(update_tx)
    
    if success:
        field, old_val, new_val = change_info
        response = (
            f"✅ *Transaction Updated*\n"
            f"🔄 Field: {field.capitalize()}\n"
            f"📍 Old: {old_val}\n"
            f"✨ New: {new_val}"
        )
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"❌ {error_msg}")



class Command(BaseCommand):
    help = "Runs the Telegram bot"

    def handle(self, *args, **options):
        import subprocess, signal, asyncio, httpx

        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            self.stdout.write(self.style.ERROR("TELEGRAM_BOT_TOKEN not found in .env"))
            return

        # --- Kill any other run_bot processes (prevent conflict) ---
        my_pid = os.getpid()
        try:
            out = subprocess.check_output(["pgrep", "-f", "run_bot"], text=True)
            for line in out.strip().split("\n"):
                pid = int(line.strip())
                if pid != my_pid:
                    self.stdout.write(f"Killing stale bot process {pid}")
                    os.kill(pid, signal.SIGKILL)
        except (subprocess.CalledProcessError, ValueError):
            pass

        # --- Force clear Telegram polling via deleteWebhook API ---
        self.stdout.write("Clearing stale Telegram connections...")
        try:
            import urllib.request
            url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
            urllib.request.urlopen(url, timeout=10)
            self.stdout.write(self.style.SUCCESS("Telegram connection cleared."))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"deleteWebhook warning: {e}"))

        import time
        time.sleep(2)

        self.stdout.write(self.style.SUCCESS("Bot is starting..."))
        app = ApplicationBuilder().token(token).build()
        
        # Add command handlers
        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("total", cmd_total))
        app.add_handler(CommandHandler("expenses", cmd_expenses))
        app.add_handler(CommandHandler("income", cmd_income))
        app.add_handler(CommandHandler("list", cmd_list))
        
        # Add message handler for text, voice, photo, and document messages
        app.add_handler(MessageHandler(
            (filters.TEXT | filters.VOICE | filters.PHOTO | filters.Document.ALL) & (~filters.COMMAND),
            handle_message
        ))
        
        app.run_polling(drop_pending_updates=True, allowed_updates=["message"])