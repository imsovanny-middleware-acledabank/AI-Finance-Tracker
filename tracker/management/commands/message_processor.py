"""Message processor — handles text, voice, photo, document messages and reply-action edits."""
import asyncio
import html
import os
import re
import uuid
from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from .bot_ui import BotUI
from .exchange_rate import fetch_usd_to_khr_rate
from .menu_service import MenuService
from .report_handler import ReportHandler
from .services_bot import analyze_finance_text, analyze_reply_action

LANG_EN = BotUI.LANG_EN
LANG_KH = BotUI.LANG_KH


def _t(lang: str, kh_text: str, en_text: str) -> str:
    return BotUI.t(lang, kh_text, en_text)


def _icon(name: str, **kwargs) -> str:
    return BotUI.icon(name, **kwargs)


def _receipt_divider() -> str:
    return BotUI.receipt_divider()


class MessageProcessor:
    """Processes incoming user messages and reply-to-message edits/deletes."""

    @staticmethod
    def _get_or_create_conversation_id(context: ContextTypes.DEFAULT_TYPE):
        """Get conversation UUID from user_data, or create one if missing/invalid."""
        raw = context.user_data.get("conversation_id")
        if raw:
            try:
                conv_id = raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw))
                context.user_data["conversation_id"] = str(conv_id)
                return conv_id
            except Exception:
                pass

        conv_id = uuid.uuid4()
        context.user_data["conversation_id"] = str(conv_id)
        return conv_id

    @staticmethod
    async def _save_chat_message(
        user_id: int, conversation_id: uuid.UUID, role: str, message: str
    ):
        """Best-effort save of Telegram AI chat history."""
        if not message:
            return

        from tracker.models import ChatMessage

        def _create():
            ChatMessage.objects.create(
                telegram_id=user_id,
                conversation_id=conversation_id,
                role=role,
                message=str(message),
            )

        try:
            await asyncio.to_thread(_create)
        except Exception:
            # Do not break user flow if history persistence fails.
            pass

    @staticmethod
    def _extract_transaction_id(original_msg: str) -> int | None:
        """Extract transaction ID from different confirmation text formats."""
        text = original_msg or ""
        patterns = [
            r"#\s*(\d+)",
            r"(?:invoice|វិក្កយបត្រ)\s*(?:id)?\s*[:：#-]?\s*(\d+)",
            r"\bid\s*[:：#-]?\s*(\d+)\b",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                try:
                    return int(m.group(1))
                except (TypeError, ValueError):
                    continue
        return None

    # ------------------------------------------------------------------ #
    # Reply-action handler (edit / delete via AI)                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    async def handle_reply_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle reply to a transaction confirmation message — edit or delete via AI."""
        from tracker.models import Transaction

        lang = BotUI.detect_user_lang(
            update, context, update.message.text if update and update.message else None
        )
        user_id = update.message.from_user.id
        reply_text = update.message.text
        original_msg = update.message.reply_to_message.text or ""

        tx_id = MessageProcessor._extract_transaction_id(original_msg)
        if tx_id is None:
            await MenuService.reply_with_menu(
                update.message,
                _t(
                    lang,
                    f"{_icon('error')} រកមិនឃើញលេខសម្គាល់ប្រតិបត្តិការនៅក្នុងសារដើមទេ។",
                    f"{_icon('error')} Cannot find transaction ID in the original message.",
                ),
                lang=lang,
            )
            return

        def get_tx():
            try:
                return Transaction.objects.get(id=tx_id, telegram_id=user_id)
            except Transaction.DoesNotExist:
                return None

        tx = await asyncio.to_thread(get_tx)
        if not tx:
            await MenuService.reply_with_menu(
                update.message,
                _t(
                    lang,
                    f"{_icon('error')} រកមិនឃើញប្រតិបត្តិការ #{tx_id} ឬអ្នកគ្មានសិទ្ធិ។",
                    f"{_icon('error')} Transaction #{tx_id} not found or unauthorized.",
                ),
                lang=lang,
            )
            return

        await MenuService.reply_with_menu(
            update.message,
            _t(
                lang,
                f"{_icon('thinking')} កំពុងវិភាគសំណើរបស់អ្នក...",
                f"{_icon('thinking')} Analyzing your request...",
            ),
            lang=lang,
        )

        try:
            action_data = await asyncio.to_thread(analyze_reply_action, reply_text, original_msg)

            if not isinstance(action_data, dict):
                raise ValueError("AI response was not a JSON object")

            action = action_data.get("action", "unknown")

            if action == "delete":
                def delete_tx():
                    info = {
                        "amount": float(tx.amount),
                        "category": tx.category_name,
                        "type": tx.transaction_type,
                        "date": tx.transaction_date.isoformat(),
                    }
                    tx.delete()
                    return info

                info = await asyncio.to_thread(delete_tx)
                tx_label_kh = "ចំណូល" if info["type"] == "income" else "ចំណាយ"
                tx_label_en = "Income" if info["type"] == "income" else "Expense"
                _date_val = info["date"]
                try:
                    from datetime import date as _dparse
                    _date_val = _dparse.fromisoformat(info["date"]).strftime("%d %b %Y")
                except Exception:
                    pass
                if lang == LANG_KH:
                    response = (
                        f"<b>\U0001f5d1 {tx_label_kh}  #{tx_id} ត្រូវបានលុប</b>\n"
                        f"<blockquote>"
                        f"ប្រភេទ  :  {tx_label_kh}\n"
                        f"ចំនួន   :  ${info['amount']:.2f}\n"
                        f"ប្រភេទ  :  {html.escape(str(info['category']))}\n"
                        f"ថ្ងៃ    :  {_date_val}"
                        f"</blockquote>"
                    )
                else:
                    response = (
                        f"<b>\U0001f5d1 {tx_label_en}  #{tx_id} Deleted</b>\n"
                        f"<blockquote>"
                        f"Type     :  {tx_label_en}\n"
                        f"Amount   :  ${info['amount']:.2f}\n"
                        f"Category :  {html.escape(str(info['category']))}\n"
                        f"Date     :  {_date_val}"
                        f"</blockquote>"
                    )
                await MenuService.reply_with_menu(
                    update.message,
                    response,
                    lang=lang,
                    parse_mode=ParseMode.HTML,
                    extra_rows=MenuService.entry_extra_rows(lang),
                )

            elif action == "edit":
                changes = action_data.get("changes", {})
                if not any(v is not None for v in changes.values()):
                    await MenuService.reply_with_menu(
                        update.message,
                        _t(
                            lang,
                            f"{_icon('info')} មិនឃើញការកែប្រែថ្មីទេ។ សូមបញ្ជាក់អ្វីដែលចង់កែ។",
                            f"{_icon('info')} No changes detected. Please specify what to edit.",
                        ),
                        lang=lang,
                        extra_rows=MenuService.entry_extra_rows(lang),
                    )
                    return

                def apply_edits():
                    from tracker.models import Category

                    updated_fields = []

                    if changes.get("amount") is not None:
                        old = float(tx.amount)
                        new_amt = Decimal(str(changes["amount"]))
                        tx.amount = new_amt
                        cur = getattr(tx, "currency", "USD") or "USD"
                        rate = asyncio.run(fetch_usd_to_khr_rate())
                        if cur == "USD":
                            tx.amount_usd = new_amt
                            tx.amount_khr = new_amt * rate
                        else:
                            tx.amount_khr = new_amt
                            tx.amount_usd = new_amt / rate if rate else new_amt
                        updated_fields.append(
                            _t(
                                lang,
                                f"ចំនួន   :  ${old:.2f}  →  ${float(new_amt):.2f}",
                                f"Amount   :  ${old:.2f}  →  ${float(new_amt):.2f}",
                            )
                        )

                    if changes.get("category") is not None:
                        old_cat = tx.category_name
                        new_cat = changes["category"]
                        try:
                            cat_obj = Category.objects.get(name__iexact=new_cat)
                        except Category.DoesNotExist:
                            cat_obj, _ = Category.objects.get_or_create(
                                name=new_cat, defaults={"icon": _icon("balance")}
                            )
                        tx.category = cat_obj
                        tx.category_name = cat_obj.name
                        updated_fields.append(
                            _t(
                                lang,
                                f"ប្រភេទ   :  {old_cat}  →  {cat_obj.name}",
                                f"Category :  {old_cat}  →  {cat_obj.name}",
                            )
                        )

                    if changes.get("date") is not None:
                        from datetime import date as _date

                        old_date = tx.transaction_date.isoformat()
                        tx.transaction_date = _date.fromisoformat(changes["date"])
                        updated_fields.append(
                            _t(
                                lang,
                                f"ថ្ងៃ     :  {old_date}  →  {changes['date']}",
                                f"Date     :  {old_date}  →  {changes['date']}",
                            )
                        )

                    if changes.get("note") is not None:
                        old_note = tx.note or "(empty)"
                        tx.note = changes["note"]
                        updated_fields.append(
                            _t(
                                lang,
                                f"ចំណាែ   :  {old_note}  →  {changes['note']}",
                                f"Note     :  {old_note}  →  {changes['note']}",
                            )
                        )

                    tx.save()
                    return updated_fields

                updated_fields = await asyncio.to_thread(apply_edits)
                rows = "\n".join(updated_fields)
                if lang == LANG_KH:
                    response = (
                        f"<b>\u270f\ufe0f បានកែប្រែ  #{tx_id}</b>\n"
                        f"<blockquote>{rows}</blockquote>"
                    )
                else:
                    response = (
                        f"<b>\u270f\ufe0f Updated  #{tx_id}</b>\n"
                        f"<blockquote>{rows}</blockquote>"
                    )
                await MenuService.reply_with_menu(
                    update.message,
                    response,
                    lang=lang,
                    parse_mode=ParseMode.HTML,
                    extra_rows=MenuService.entry_extra_rows(lang),
                )

            else:
                msg = action_data.get("message", "I could not understand your request.")
                await MenuService.reply_with_menu(
                    update.message,
                    f"{_icon('question')} {msg}\n\n"
                    f"{_icon('tip')} *ណែនាំ:* ឆ្លើយតបដូចខាងក្រោម៖\n"
                    f'• "delete" ឬ "លុប" ដើម្បីលុប\n'
                    f'• "change amount to 50" ឬ "កែតម្លៃ 50" ដើម្បីកែ',
                    parse_mode=ParseMode.MARKDOWN,
                    lang=lang,
                    extra_rows=MenuService.entry_extra_rows(lang),
                )

        except Exception as e:
            await MenuService.reply_with_menu(
                update.message,
                _t(
                    lang,
                    f"{_icon('error')} មានបញ្ហា៖ {str(e)}",
                    f"{_icon('error')} Error: {str(e)}",
                ),
                lang=lang,
                extra_rows=MenuService.entry_extra_rows(lang),
            )

    # ------------------------------------------------------------------ #
    # Main message handler                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process text, voice, photos, and documents for financial transactions."""
        if not update.message:
            return

        lang = BotUI.detect_user_lang(update, context)
        currency_mode = MenuService.normalize_currency_mode(
            context.user_data.get("currency_view")
        )
        context.user_data["currency_view"] = currency_mode

        replied_text = (
            (update.message.reply_to_message.text or "")
            if update.message.reply_to_message
            else ""
        )
        is_tx_confirmation = (
            MessageProcessor._extract_transaction_id(replied_text) is not None
            and (
                "Recorded" in replied_text
                or "បានកត់ត្រា" in replied_text
                or "Invoice" in replied_text
                or "វិក្កយបត្រ" in replied_text
            )
        )

        if (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user
            and update.message.reply_to_message.from_user.is_bot
            and update.message.text
            and is_tx_confirmation
        ):
            await MessageProcessor.handle_reply_action(update, context)
            return

        user_input = None
        user_id = update.message.from_user.id

        if update.message.text:
            user_input = update.message.text

        elif update.message.voice:
            try:
                thinking_msg = await MenuService.reply_with_menu(
                    update.message,
                    _t(lang, f"{_icon('mic')} កំពុងស្តាប់សារសំឡេង...", f"{_icon('mic')} Processing voice message..."),
                    lang=lang,
                    extra_rows=MenuService.entry_extra_rows(lang),
                )
                await update.message.chat.send_action(ChatAction.TYPING)

                voice_file = await context.bot.get_file(update.message.voice.file_id)
                voice_bytes = await voice_file.download_as_bytearray()

                def process_voice_with_gemini(audio_data):
                    import google.generativeai as genai

                    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                    candidate_models = [
                        "models/gemini-2.5-flash",
                        "models/gemini-2.0-flash",
                        "models/gemini-2.5-flash-lite",
                    ]
                    prompt = (
                        "Listen to this voice message and transcribe exactly what the user said. "
                        "Then respond with ONLY the transcribed text, nothing else. "
                        "The user may speak in Khmer (ខ្មែរ) or English. "
                        "If the audio is unclear or too short, respond with: UNCLEAR_AUDIO"
                    )
                    audio_part = {"mime_type": "audio/ogg", "data": bytes(audio_data)}
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

                if not transcribed or transcribed == "UNCLEAR_AUDIO":
                    await MenuService.reply_with_menu(
                        update.message,
                        _t(lang, f"{_icon('mic')} មិនអាចស្តាប់សារសំឡេងបានច្បាស់ទេ។ សូមព្យាយាមម្ដងទៀត។", f"{_icon('mic')} Could not understand the voice message. Please try again."),
                        lang=lang,
                        extra_rows=MenuService.entry_extra_rows(lang),
                    )
                    return

                user_input = transcribed
                lang = BotUI.detect_user_lang(update, context, user_input)
                await MenuService.reply_with_menu(
                    update.message,
                    _t(lang, f"{_icon('mic')} *ស្តាប់បាន:* {user_input}", f"{_icon('mic')} *Heard:* {user_input}"),
                    lang=lang,
                    parse_mode=ParseMode.MARKDOWN,
                    extra_rows=MenuService.entry_extra_rows(lang),
                )

            except Exception as e:
                await MenuService.reply_with_menu(
                    update.message,
                    _t(lang, f"{_icon('error')} មានបញ្ហាពេលដំណើរការសំឡេង៖ {str(e)}", f"{_icon('error')} Voice processing error: {str(e)}"),
                    lang=lang,
                    extra_rows=MenuService.entry_extra_rows(lang),
                )
                return

        elif update.message.photo:
            try:
                thinking_msg = await MenuService.reply_with_menu(
                    update.message,
                    _t(lang, f"{_icon('camera')} កំពុងអានរូបភាព...", f"{_icon('camera')} Reading image..."),
                    lang=lang,
                    extra_rows=MenuService.entry_extra_rows(lang),
                )
                await update.message.chat.send_action(ChatAction.TYPING)

                photo = update.message.photo[-1]
                photo_file = await context.bot.get_file(photo.file_id)
                photo_bytes = await photo_file.download_as_bytearray()
                caption = update.message.caption or ""

                def analyze_photo_with_gemini(img_data, caption_text):
                    import google.generativeai as genai

                    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                    candidate_models = [
                        "models/gemini-2.5-flash",
                        "models/gemini-2.0-flash",
                        "models/gemini-2.5-flash-lite",
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
                    image_part = {"mime_type": "image/jpeg", "data": bytes(img_data)}
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
                    await MenuService.reply_with_menu(
                        update.message,
                        _t(lang, f"{_icon('camera')} មិនអាចអានរូបភាពបានទេ។ សូមព្យាយាមម្ដងទៀត។", f"{_icon('camera')} Could not read the image. Please try again."),
                        lang=lang,
                        extra_rows=MenuService.entry_extra_rows(lang),
                    )
                    return

                user_input = result
                lang = BotUI.detect_user_lang(update, context, user_input)
                await MenuService.reply_with_menu(
                    update.message,
                    _t(lang, f"{_icon('camera')} *អានបាន:* {user_input}", f"{_icon('camera')} *Read:* {user_input}"),
                    lang=lang,
                    parse_mode=ParseMode.MARKDOWN,
                    extra_rows=MenuService.entry_extra_rows(lang),
                )

            except Exception as e:
                await MenuService.reply_with_menu(
                    update.message,
                    _t(lang, f"{_icon('error')} មានបញ្ហាពេលអានរូបភាព៖ {str(e)}", f"{_icon('error')} Photo processing error: {str(e)}"),
                    lang=lang,
                    extra_rows=MenuService.entry_extra_rows(lang),
                )
                return

        elif update.message.document:
            if update.message.caption:
                user_input = update.message.caption
            else:
                await MenuService.reply_with_menu(
                    update.message,
                    _t(lang, f"{_icon('document')} សូមភ្ជាប់ caption ជាមួយឯកសារ ដូចជា 'ចំណាយ $5 អាហារ'។", f"{_icon('document')} Please include a caption with the document, e.g. 'spent $5 on lunch'."),
                    lang=lang,
                    extra_rows=MenuService.entry_extra_rows(lang),
                )
                return

        else:
            await MenuService.reply_with_menu(
                update.message,
                _t(
                    lang,
                    f"{_icon('info')} ខ្ញុំអាចដំណើរការសារអក្សរ សារសំឡេង រូបភាព និងឯកសារដែលមាន caption បាន។\nសាកផ្ញើសារដូចជា 'ចំណាយ $5 អាហារ' ឬឆ្លើយតបទៅ media ជាមួយ caption។",
                    f"{_icon('info')} I can process text, voice, photos, and documents with captions.\nSend a message like 'spent $5 on lunch' or reply to media with a caption.",
                ),
                lang=lang,
                extra_rows=MenuService.entry_extra_rows(lang),
            )
            return

        if not user_input:
            return

        try:
            lang = BotUI.detect_user_lang(update, context, user_input)
            thinking_msg = await MenuService.reply_with_menu(
                update.message,
                _t(lang, f"{_icon('thinking')} កំពុងវិភាគសំណើរបស់អ្នក...", f"{_icon('thinking')} Analyzing your request..."),
                lang=lang,
            )
            await update.message.chat.send_action(ChatAction.TYPING)

            data = await asyncio.to_thread(analyze_finance_text, user_input)

            try:
                await thinking_msg.delete()
            except Exception:
                pass

            if not isinstance(data, dict):
                raise ValueError("AI response was not a JSON object")

            if not data.get("is_transaction", True):
                conversation_id = MessageProcessor._get_or_create_conversation_id(context)
                await MessageProcessor._save_chat_message(
                    user_id, conversation_id, "user", user_input
                )

                if data.get("is_summary"):
                    await MessageProcessor._save_chat_message(
                        user_id,
                        conversation_id,
                        "ai",
                        data.get(
                            "message",
                            _t(
                                lang,
                                "បានទទួលសំណើសង្ខេបហិរញ្ញវត្ថុ។",
                                "Summary request received.",
                            ),
                        ),
                    )
                    await ReportHandler.handle_summary(update, user_id, data, lang, currency_mode=currency_mode)
                    return
                if data.get("is_balance"):
                    await MessageProcessor._save_chat_message(
                        user_id,
                        conversation_id,
                        "ai",
                        data.get(
                            "message",
                            _t(
                                lang,
                                "បានទទួលសំណើពិនិត្យសមតុល្យ។",
                                "Balance request received.",
                            ),
                        ),
                    )
                    await ReportHandler.handle_balance_currency(update, user_id, lang, currency_mode)
                    return
                response = data.get(
                    "message",
                    _t(lang, "នេះមិនមែនជាប្រតិបត្តិការហិរញ្ញវត្ថុទេ។", "This does not appear to be a financial transaction."),
                )
                await MessageProcessor._save_chat_message(
                    user_id, conversation_id, "ai", response
                )
                await MenuService.reply_with_menu(
                    update.message,
                    f"{_icon('info')} {response}",
                    lang=lang,
                    extra_rows=MenuService.help_extra_rows(lang, currency_mode=currency_mode),
                )
                return

            if not data.get("amount"):
                raise ValueError("Parsed data missing required field: amount")
            if not data.get("type"):
                raise ValueError("Parsed data missing required field: type")
            # Apply smart category defaults: income with no specified source → Salary
            if not data.get("category") or (
                data.get("type") == "income" and data.get("category", "").strip().lower() == "other"
            ):
                data["category"] = "Salary" if data.get("type") == "income" else "Other"

            def parse_amount(value):
                if isinstance(value, (int, float, Decimal)):
                    return Decimal(str(value))
                if isinstance(value, str):
                    cleaned = value.replace("$", "").replace(",", "").strip()
                    return Decimal(cleaned)
                raise InvalidOperation("unsupported amount type")

            try:
                amount_dec = parse_amount(data["amount"])
            except (InvalidOperation, ValueError) as e:
                raise ValueError(f"Could not parse amount: {e}")

            def parse_date(value):
                from datetime import date as _date
                from datetime import datetime

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
                        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                            try:
                                return datetime.strptime(value, fmt).date()
                            except Exception:
                                continue
                raise ValueError("Unsupported date format")

            from datetime import date as _date

            try:
                tx_date = parse_date(data.get("date"))
            except ValueError:
                tx_date = _date.today()

            tx_type = str(data.get("type")).lower()
            if tx_type not in ("income", "expense"):
                raise ValueError("Parsed field 'type' must be 'income' or 'expense'")

            from tracker.models import Category, Transaction

            category_name = data.get("category", "Other")
            category, _ = await asyncio.to_thread(
                Category.objects.get_or_create,
                name=category_name,
                defaults={"icon": _icon("balance")},
            )

            currency = data.get("currency", "USD").upper()
            if currency not in ("USD", "KHR"):
                currency = "USD"

            rate = await fetch_usd_to_khr_rate()
            if currency == "USD":
                amount_usd = amount_dec
                amount_khr = amount_dec * rate
            else:
                amount_khr = amount_dec
                amount_usd = amount_dec / rate if rate else amount_dec

            create_kwargs = {
                "telegram_id": user_id,
                "amount": amount_dec,
                "currency": currency,
                "amount_usd": amount_usd,
                "amount_khr": amount_khr,
                "category_name": category_name,
                "category": category,
                "transaction_type": tx_type,
                "note": data.get("note"),
                "transaction_date": tx_date,
                "is_recurring": False,
                "tags": "",
            }
            tx = await asyncio.to_thread(Transaction.objects.create, **create_kwargs)

            tx_sequence = await asyncio.to_thread(
                lambda: Transaction.objects.filter(
                    telegram_id=user_id, transaction_type=tx_type
                ).count()
            )

            # Budget alert
            if tx_type == "expense":
                from tracker.models import Budget

                def get_budgets():
                    return list(
                        Budget.objects.filter(
                            telegram_id=user_id,
                            category=category,
                            frequency="monthly",
                            is_active=True,
                        )
                    )

                budgets = await asyncio.to_thread(get_budgets)
                for budget in budgets:
                    if budget.get_percentage_used() > budget.alert_threshold:
                        await MenuService.send_with_menu(
                            context.bot,
                            user_id,
                            _t(
                                lang,
                                f"{_icon('warning')} ថវិកា {budget.category.name}: {budget.get_percentage_used():.0f}% (${budget.get_spent_amount():.2f}/{budget.limit_amount:.2f})",
                                f"{_icon('warning')} Budget {budget.category.name}: {budget.get_percentage_used():.0f}% (${budget.get_spent_amount():.2f}/{budget.limit_amount:.2f})",
                            ),
                            lang=lang,
                            parse_mode=ParseMode.MARKDOWN,
                            extra_rows=MenuService.report_extra_rows(lang, currency_mode=currency_mode),
                        )

            currency_symbol = "$" if currency == "USD" else "៛"
            note_val = html.escape(str(data.get("note") or ""))
            cat_val = html.escape(category_name)
            date_val = tx_date.strftime("%d %b %Y")
            if currency_mode == "KHR":
                converted_label_kh = "តម្លៃបង្ហាញ"
                converted_label_en = "Display"
                converted_amount = f"៛{amount_khr:,.0f}"
            else:
                converted_label_kh = "តម្លៃបង្ហាញ"
                converted_label_en = "Display"
                converted_amount = f"${amount_usd:,.2f}"
            if lang == LANG_KH:
                tx_label = "ចំណូល" if tx_type == "income" else "ចំណាយ"
                response = (
                    f"<b>{tx_label}</b>\n"
                    f"<blockquote>"
                    f"វិក្កយបត្រ :  {tx.id}\n"
                    f"{tx_label}លើកទី :  {tx_sequence}\n"
                    f"ចំនួន      :  {currency_symbol}{amount_dec:,.2f} ({currency})\n"
                    f"{converted_label_kh} :  {converted_amount}\n"
                    f"ប្រភេទ     :  {cat_val}\n"
                    f"ចំណាំ      :  {note_val or 'មិនមាន'}\n"
                    f"ថ្ងៃ       :  {date_val}"
                    f"</blockquote>\n"
                    f"<i>ឆ្លើយតបសារនេះ ដើម្បីកែ ឬ លុប</i>"
                )
            else:
                tx_label = "Income" if tx_type == "income" else "Expense"
                response = (
                    f"<b>✅ {tx_label}</b>\n"
                    f"<blockquote>"
                    f"Invoice  :  {tx.id}\n"
                    f"{tx_label} Entry No. :  {tx_sequence}\n"
                    f"Amount   :  {currency_symbol}{amount_dec:,.2f} ({currency})\n"
                    f"{converted_label_en} :  {converted_amount}\n"
                    f"Category :  {cat_val}\n"
                    f"Note     :  {note_val or 'N/A'}\n"
                    f"Date     :  {date_val}"
                    f"</blockquote>\n"
                    f"<i>Reply to this message to edit or delete</i>"
                )
            await MenuService.reply_with_menu(
                update.message,
                response,
                lang=lang,
                parse_mode=ParseMode.HTML,
                extra_rows=MenuService.entry_extra_rows(lang),
            )

            # Balance alert
            if tx_type == "expense":
                def check_balance():
                    from django.db.models import Sum

                    total_income = Transaction.objects.filter(
                        telegram_id=user_id, transaction_type="income"
                    ).aggregate(total=Sum("amount_usd"))["total"] or Decimal("0")
                    total_expense = Transaction.objects.filter(
                        telegram_id=user_id, transaction_type="expense"
                    ).aggregate(total=Sum("amount_usd"))["total"] or Decimal("0")
                    return total_income, total_expense

                total_income, total_expense = await asyncio.to_thread(check_balance)
                net = total_income - total_expense

                if net < 0:
                    rate = await fetch_usd_to_khr_rate()
                    deficit_usd = abs(net)
                    deficit_khr = deficit_usd * rate
                    if currency_mode == "KHR":
                        income_display = f"៛{total_income * rate:,.0f}"
                        expense_display = f"៛{total_expense * rate:,.0f}"
                        deficit_display = f"-៛{deficit_khr:,.0f}"
                    else:
                        income_display = f"${total_income:,.2f}"
                        expense_display = f"${total_expense:,.2f}"
                        deficit_display = f"-${deficit_usd:,.2f}"
                    alert = _t(
                        lang,
                        f"{_icon('warning')} *ការជូនដំណឹងសមតុល្យ*\n\n{_icon('warning')} ចំណាយលើសចំណូល!\n\n{_icon('warning')} ចំណូលសរុប: {income_display}\n{_icon('warning')} ចំណាយសរុប: {expense_display}\n{_icon('warning')} ខ្វះ: {deficit_display}\n\n{_icon('warning')} *ណែនាំ:* សូមកាត់បន្ថយចំណាយ ឬបន្ថែមចំណូល។",
                        f"{_icon('warning')} *Available Balance Alert*\n\n{_icon('warning')} Expenses exceed income!\n\n{_icon('warning')} Total Income: {income_display}\n{_icon('warning')} Total Expenses: {expense_display}\n{_icon('warning')} Deficit: {deficit_display}\n\n{_icon('warning')} *Tip:* Consider reducing expenses or adding income.",
                    )
                    await MenuService.send_with_menu(
                        context.bot,
                        user_id,
                        alert,
                        lang=lang,
                        parse_mode=ParseMode.MARKDOWN,
                        extra_rows=MenuService.entry_extra_rows(lang),
                    )

        except Exception as e:
            err_msg = str(e)
            if "quota" in err_msg.lower() or "rate" in err_msg.lower() or "429" in err_msg:
                await MenuService.reply_with_menu(
                    update.message,
                    _t(lang, "⏳ សេវា AI រវល់បណ្ដោះអាសន្ន។ សូមព្យាយាមម្ដងទៀតក្នុង 1 នាទី។", "⏳ AI service is temporarily busy. Please try again in 1 minute."),
                    lang=lang,
                    extra_rows=MenuService.entry_extra_rows(lang),
                )
            else:
                if len(err_msg) > 300:
                    err_msg = err_msg[:300] + "..."
                await MenuService.reply_with_menu(
                    update.message,
                    _t(lang, f"{_icon('error')} មានបញ្ហា៖ {err_msg}", f"{_icon('error')} Error: {err_msg}"),
                    lang=lang,
                    extra_rows=MenuService.entry_extra_rows(lang),
                )


# Module-level shortcuts
handle_message = MessageProcessor.handle_message
handle_reply_action = MessageProcessor.handle_reply_action
