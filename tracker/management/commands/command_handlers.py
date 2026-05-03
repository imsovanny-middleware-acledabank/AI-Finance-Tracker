"""Command handlers — /start, /help, /total, /expenses, /income, /list, /delete, /edit, /rate."""
import asyncio
import logging
from decimal import Decimal

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from .bot_ui import BotUI
from .exchange_rate import USD_KHR_FALLBACK_RATE, fetch_usd_to_khr_rate
from .menu_service import MenuService

LANG_EN = BotUI.LANG_EN
LANG_KH = BotUI.LANG_KH

logger = logging.getLogger(__name__)


def _t(lang: str, kh_text: str, en_text: str) -> str:
    return BotUI.t(lang, kh_text, en_text)


def _icon(name: str, **kwargs) -> str:
    return BotUI.icon(name, **kwargs)


def log_action(action: str, **kwargs):
    details = ", ".join(
        f"{key}={value!r}" for key, value in kwargs.items() if value is not None
    )
    logger.info("%s%s", action, f" | {details}" if details else "")


class BotCommandHandlers:
    """All /command handlers for the Telegram bot."""

    @staticmethod
    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show start message with dashboard link."""
        user_id = update.message.from_user.id
        user = update.message.from_user
        user_name = user.first_name or ""
        if user.last_name:
            user_name = f"{user_name} {user.last_name}".strip()
        if not user_name.strip():
            user_name = "User"
        log_action("cmd_start", user_id=user_id, user_name=user_name)
        lang = BotUI.detect_user_lang(update, context)
        currency_mode = MenuService.normalize_currency_mode(
            context.user_data.get("currency_view")
        )
        context.user_data["currency_view"] = currency_mode
        context.user_data["menu_stack"] = [("main", {})]
        context.user_data["nav_stack"] = [{"state": "main", "data": {}}]
        await MenuService.reply_with_menu(
            update.message,
            MenuService.start_help_text(lang, user_name, user_id, MenuService.public_app_url()),
            lang=lang,
            parse_mode=ParseMode.HTML,
            extra_rows=None,
        )

    @staticmethod
    async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help and quick action buttons."""
        user_id = update.message.from_user.id
        user = update.message.from_user
        user_name = user.first_name or ""
        if user.last_name:
            user_name = f"{user_name} {user.last_name}".strip()
        if not user_name.strip():
            user_name = "User"
        log_action("cmd_help", user_id=user_id, user_name=user_name)
        lang = BotUI.detect_user_lang(update, context)
        currency_mode = MenuService.normalize_currency_mode(
            context.user_data.get("currency_view")
        )
        await MenuService.send_help_message(
            update.message, user_name, user_id, lang, currency_mode=currency_mode
        )

    @staticmethod
    async def cmd_total(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show total expenses and income."""
        from django.db.models import Sum

        from tracker.models import Transaction

        user_id = update.message.from_user.id
        lang = BotUI.detect_user_lang(update, context)
        currency_mode = MenuService.normalize_currency_mode(
            context.user_data.get("currency_view")
        )

        def fetch_totals():
            expenses_usd = Transaction.objects.filter(
                telegram_id=user_id, transaction_type="expense"
            ).aggregate(total=Sum("amount_usd"))["total"] or Decimal("0")
            income_usd = Transaction.objects.filter(
                telegram_id=user_id, transaction_type="income"
            ).aggregate(total=Sum("amount_usd"))["total"] or Decimal("0")
            return expenses_usd, income_usd

        expenses_usd, income_usd = await asyncio.to_thread(fetch_totals)
        net_usd = income_usd - expenses_usd
        rate = await fetch_usd_to_khr_rate()
        if currency_mode == "KHR":
            expenses_display = f"៛{expenses_usd * rate:,.0f}"
            income_display = f"៛{income_usd * rate:,.0f}"
            net_display = f"៛{net_usd * rate:,.0f}"
        else:
            expenses_display = f"${expenses_usd:,.2f}"
            income_display = f"${income_usd:,.2f}"
            net_display = f"${net_usd:,.2f}"
        if lang == LANG_KH:
            response = (
                f"{_icon('balance')} *សង្ខេបហិរញ្ញវត្ថុ*\n\n"
                f"{_icon('expense')} ចំណាយសរុប៖\n"
                f"   {expenses_display}\n\n"
                f"{_icon('income')} ចំណូលសរុប៖\n"
                f"   {income_display}\n\n"
                f"{_icon('summary')} សរុបនៅសល់៖\n"
                f"   {net_display}"
            )
        else:
            response = (
                f"{_icon('balance')} *Financial Summary*\n\n"
                f"{_icon('expense')} Total Expenses:\n"
                f"   {expenses_display}\n\n"
                f"{_icon('income')} Total Income:\n"
                f"   {income_display}\n\n"
                f"{_icon('summary')} Net Balance:\n"
                f"   {net_display}"
            )
        await MenuService.reply_with_menu(
            update.message,
            response,
            lang=lang,
            parse_mode=ParseMode.MARKDOWN,
            extra_rows=MenuService.report_extra_rows(lang, currency_mode=currency_mode),
        )

    @staticmethod
    async def cmd_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show total expenses."""
        from django.db.models import Sum

        from tracker.models import Transaction

        user_id = update.message.from_user.id
        lang = BotUI.detect_user_lang(update, context)
        currency_mode = MenuService.normalize_currency_mode(
            context.user_data.get("currency_view")
        )

        def fetch_expenses():
            total_usd = Transaction.objects.filter(
                telegram_id=user_id, transaction_type="expense"
            ).aggregate(total=Sum("amount_usd"))["total"] or Decimal("0")
            count = Transaction.objects.filter(
                telegram_id=user_id, transaction_type="expense"
            ).count()
            return total_usd, count

        total_usd, count = await asyncio.to_thread(fetch_expenses)
        rate = await fetch_usd_to_khr_rate()
        total_display = f"៛{total_usd * rate:,.0f}" if currency_mode == "KHR" else f"${total_usd:,.2f}"
        response = _t(
            lang,
            f"{_icon('expense')} ចំណាយសរុប: {total_display} ({count} ប្រតិបត្តិការ)",
            f"{_icon('expense')} Total Expenses: {total_display} ({count} transactions)",
        )
        await MenuService.reply_with_menu(
            update.message,
            response,
            lang=lang,
            parse_mode=ParseMode.MARKDOWN,
            extra_rows=MenuService.report_extra_rows(lang, currency_mode=currency_mode),
        )

    @staticmethod
    async def cmd_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show total income."""
        from django.db.models import Sum

        from tracker.models import Transaction

        user_id = update.message.from_user.id
        lang = BotUI.detect_user_lang(update, context)
        currency_mode = MenuService.normalize_currency_mode(
            context.user_data.get("currency_view")
        )

        def fetch_income():
            total_usd = Transaction.objects.filter(
                telegram_id=user_id, transaction_type="income"
            ).aggregate(total=Sum("amount_usd"))["total"] or Decimal("0")
            count = Transaction.objects.filter(
                telegram_id=user_id, transaction_type="income"
            ).count()
            return total_usd, count

        total_usd, count = await asyncio.to_thread(fetch_income)
        rate = await fetch_usd_to_khr_rate()
        total_display = f"៛{total_usd * rate:,.0f}" if currency_mode == "KHR" else f"${total_usd:,.2f}"
        response = _t(
            lang,
            f"{_icon('income')} ចំណូលសរុប: {total_display} ({count} ប្រតិបត្តិការ)",
            f"{_icon('income')} Total Income: {total_display} ({count} transactions)",
        )
        await MenuService.reply_with_menu(
            update.message,
            response,
            lang=lang,
            parse_mode=ParseMode.MARKDOWN,
            extra_rows=MenuService.report_extra_rows(lang, currency_mode=currency_mode),
        )

    @staticmethod
    async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent transactions."""
        user_id = update.message.from_user.id
        lang = BotUI.detect_user_lang(update, context)
        currency_mode = MenuService.normalize_currency_mode(
            context.user_data.get("currency_view")
        )
        await MenuService.send_recent_transactions(
            update.message, user_id, lang, currency_mode=currency_mode
        )

    @staticmethod
    async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete a transaction by ID. Usage: /delete <transaction_id>"""
        from tracker.models import Transaction

        user_id = update.message.from_user.id
        log_action("cmd_delete", user_id=user_id)
        lang = BotUI.detect_user_lang(update, context)

        if not context.args:
            await MenuService.reply_with_menu(
                update.message,
                _t(
                    lang,
                    f"{_icon('error')} របៀបប្រើ: /delete <transaction_id>\nឧទាហរណ៍: /delete 42\nប្រើ /list ដើម្បីមើលលេខសម្គាល់ប្រតិបត្តិការ",
                    f"{_icon('error')} Usage: /delete <transaction_id>\nExample: /delete 42\nUse /list to see transaction IDs",
                ),
                lang=lang,
            )
            return

        try:
            transaction_id = int(context.args[0])
        except ValueError:
            await MenuService.reply_with_menu(
                update.message,
                _t(lang, f"{_icon('error')} Transaction ID ត្រូវតែជាលេខ", f"{_icon('error')} Transaction ID must be a number"),
                lang=lang,
            )
            return

        def delete_tx():
            try:
                tx = Transaction.objects.get(id=transaction_id, telegram_id=user_id)
                tx_info = {
                    "id": tx.id,
                    "amount": float(tx.amount),
                    "category": tx.category_name,
                    "date": tx.transaction_date.isoformat(),
                    "type": tx.transaction_type,
                }
                tx.delete()
                return True, tx_info
            except Transaction.DoesNotExist:
                return False, None

        success, tx_info = await asyncio.to_thread(delete_tx)

        if success:
            icon = _icon("tx_type", tx_type=tx_info["type"])
            response = _t(
                lang,
                f"{_icon('success')} *បានលុបប្រតិបត្តិការ*\n{icon} ប្រភេទ: {tx_info['type'].capitalize()}\n{_icon('balance')} ចំនួន: ${tx_info['amount']:.2f}\n{_icon('category')} ប្រភេទចំណាយ: {tx_info['category']}\n{_icon('today')} កាលបរិច្ឆេទ: {tx_info['date']}",
                f"{_icon('success')} *Transaction Deleted*\n{icon} Type: {tx_info['type'].capitalize()}\n{_icon('balance')} Amount: ${tx_info['amount']:.2f}\n{_icon('category')} Category: {tx_info['category']}\n{_icon('today')} Date: {tx_info['date']}",
            )
            await MenuService.reply_with_menu(
                update.message, response, lang=lang, parse_mode=ParseMode.MARKDOWN
            )
        else:
            await MenuService.reply_with_menu(
                update.message,
                _t(lang, f"{_icon('error')} រកមិនឃើញប្រតិបត្តិការ #{transaction_id} ឬអ្នកគ្មានសិទ្ធិ", f"{_icon('error')} Transaction #{transaction_id} not found or unauthorized"),
                lang=lang,
            )

    @staticmethod
    async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Edit a transaction. Usage: /edit <id> <field> <value>"""
        from tracker.models import Transaction

        user_id = update.message.from_user.id
        log_action("cmd_edit", user_id=user_id)
        lang = BotUI.detect_user_lang(update, context)

        if len(context.args) < 3:
            await MenuService.reply_with_menu(
                update.message,
                _t(
                    lang,
                    f"{_icon('error')} របៀបប្រើ: /edit <id> <field> <value>\n\nវាលអាចកែបាន:\n• amount - /edit 42 amount 50\n• category - /edit 42 category Food\n• date - /edit 42 date 2026-04-19\n• note - /edit 42 note lunch at cafe\n\nប្រើ /list ដើម្បីមើលលេខសម្គាល់ប្រតិបត្តិការ",
                    f"{_icon('error')} Usage: /edit <id> <field> <value>\n\nFields:\n• amount - /edit 42 amount 50\n• category - /edit 42 category Food\n• date - /edit 42 date 2026-04-19\n• note - /edit 42 note lunch at cafe\n\nUse /list to see transaction IDs",
                ),
                lang=lang,
            )
            return

        try:
            transaction_id = int(context.args[0])
            field = context.args[1].lower()
            value = " ".join(context.args[2:])
        except (ValueError, IndexError):
            await MenuService.reply_with_menu(
                update.message,
                _t(lang, f"{_icon('error')} ទម្រង់បញ្ជាមិនត្រឹមត្រូវ", f"{_icon('error')} Invalid format"),
                lang=lang,
            )
            return

        def update_tx():
            from datetime import datetime

            from tracker.models import Category

            try:
                tx = Transaction.objects.get(id=transaction_id, telegram_id=user_id)
                old_value = None

                if field == "amount":
                    try:
                        old_value = float(tx.amount)
                        tx.amount = float(value)
                    except ValueError:
                        return False, None, "Invalid amount"
                elif field == "category":
                    try:
                        old_value = tx.category_name
                        category = Category.objects.get(name__iexact=value)
                        tx.category = category
                        tx.category_name = category.name
                    except Category.DoesNotExist:
                        return False, None, f"Category '{value}' not found"
                elif field == "date":
                    try:
                        old_value = tx.transaction_date.isoformat()
                        tx.transaction_date = datetime.fromisoformat(value).date()
                    except (ValueError, AttributeError):
                        return False, None, "Invalid date (use YYYY-MM-DD)"
                elif field == "note":
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
            response = _t(
                lang,
                f"{_icon('success')} *បានកែប្រែប្រតិបត្តិការ*\n{_icon('update')} វាល: {field.capitalize()}\n{_icon('old')} ចាស់: {old_val}\n{_icon('new')} ថ្មី: {new_val}",
                f"{_icon('success')} *Transaction Updated*\n{_icon('update')} Field: {field.capitalize()}\n{_icon('old')} Old: {old_val}\n{_icon('new')} New: {new_val}",
            )
            await MenuService.reply_with_menu(
                update.message, response, lang=lang, parse_mode=ParseMode.MARKDOWN
            )
        else:
            await MenuService.reply_with_menu(
                update.message, f"{_icon('error')} {error_msg}", lang=lang
            )

    @staticmethod
    async def cmd_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show the current USD→KHR exchange rate from the API."""
        lang = BotUI.detect_user_lang(update, context)
        try:
            rate = await fetch_usd_to_khr_rate(force_refresh=True)
            if rate == USD_KHR_FALLBACK_RATE:
                msg = _t(
                    lang,
                    f"{_icon('fx')} តម្លៃប្តូរប្រាក់ (API fallback): 1 USD ≈ ៛{rate:,.0f}\n(មិនអាចទាក់ទង API តម្លៃពិតបាន)",
                    f"{_icon('fx')} Exchange Rate (API fallback): 1 USD ≈ ៛{rate:,.0f}\n(Could not fetch real-time rate)",
                )
            else:
                msg = _t(
                    lang,
                    f"{_icon('fx')} តម្លៃប្តូរប្រាក់បច្ចុប្បន្ន៖ 1 USD ≈ ៛{rate:,.2f}",
                    f"{_icon('fx')} Current Exchange Rate: 1 USD ≈ ៛{rate:,.2f}",
                )
        except Exception as e:
            msg = _t(
                lang,
                f"{_icon('error')} មិនអាចយកតម្លៃប្តូរប្រាក់ពី API បានទេ!\n{e}",
                f"{_icon('error')} Could not fetch exchange rate from API!\n{e}",
            )
        await MenuService.reply_with_menu(update.message, msg, lang=lang)

    @classmethod
    def register_all(cls, app) -> None:
        """Register all command handlers with the Application."""
        from telegram.ext import CommandHandler

        app.add_handler(CommandHandler("start", cls.cmd_start))
        app.add_handler(CommandHandler("help", cls.cmd_help))
        app.add_handler(CommandHandler("total", cls.cmd_total))
        app.add_handler(CommandHandler("expenses", cls.cmd_expenses))
        app.add_handler(CommandHandler("income", cls.cmd_income))
        app.add_handler(CommandHandler("list", cls.cmd_list))
        app.add_handler(CommandHandler("delete", cls.cmd_delete))
        app.add_handler(CommandHandler("edit", cls.cmd_edit))
        app.add_handler(CommandHandler("rate", cls.cmd_rate))
