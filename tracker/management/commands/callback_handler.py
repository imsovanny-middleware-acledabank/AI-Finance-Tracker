"""Callback handler — processes all InlineKeyboard button presses."""
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .bot_ui import BotUI
from .buttons import build_help_support_rows, make_callback_button
from .menu_service import MenuService
from .navigation import current_state, on_back, on_next
from .report_handler import ReportHandler
from .ui_texts import BotUITexts

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


def _usage_instructions(lang: str) -> str:
    return BotUITexts.usage_instructions(lang, _t, _icon, LANG_KH)


class CallbackHandler:
    """Handles all Telegram InlineKeyboard callback queries."""

    @staticmethod
    async def handle_quick_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if not query:
            return

        log_action(
            action="button_press",
            user_id=query.from_user.id if query and query.from_user else None,
            user_name=(
                query.from_user.first_name
                + (" " + query.from_user.last_name if query.from_user.last_name else "")
            )
            if query and query.from_user
            else None,
            button_action=query.data if query else None,
            chat_id=query.message.chat_id if query and query.message else None,
            message_id=query.message.message_id if query and query.message else None,
        )

        await query.answer()

        action = query.data or ""
        user_id = query.from_user.id
        user = query.from_user
        user_name = user.first_name or ""
        if user.last_name:
            user_name = f"{user_name} {user.last_name}".strip()
        if not user_name.strip():
            user_name = "User"

        lang = BotUI.detect_user_lang(update, context)
        currency_mode = MenuService.normalize_currency_mode(
            context.user_data.get("currency_view")
        )
        context.user_data["currency_view"] = currency_mode

        if not context.user_data.get("nav_stack"):
            context.user_data["nav_stack"] = [{"state": "main", "data": {}}]

        # ---------------------------------------------------------------- #
        # Inner helper: render a named state                                #
        # ---------------------------------------------------------------- #
        async def _render_state(state_name: str | None):
            state_name = state_name or "main"
            if state_name == "main":
                await MenuService.send_main_menu(query.message, user_name, user_id, lang)
                return
            if state_name == "all_buttons":
                await MenuService.reply_with_menu(
                    query.message,
                    MenuService.start_help_text(
                        lang, user_name, user_id, MenuService.public_app_url()
                    ),
                    lang=lang,
                    parse_mode=ParseMode.HTML,
                    extra_rows=MenuService.all_buttons_extra_rows(lang),
                )
                return
            if state_name == "add_expense":
                await MenuService.send_quick_entry_help(query.message, "expense", lang)
                return
            if state_name == "add_income":
                await MenuService.send_quick_entry_help(query.message, "income", lang)
                return
            if state_name in {"help", "usage_instructions"}:
                help_support_rows = build_help_support_rows(
                    lang, context.user_data.get("nav_stack", [])
                )
                await MenuService.reply_with_menu(
                    query.message,
                    _usage_instructions(lang),
                    lang=lang,
                    parse_mode=ParseMode.HTML,
                    extra_rows=help_support_rows,
                )
                return
            if state_name == "today":
                await ReportHandler.handle_summary(
                    query,
                    user_id,
                    {"period": "day"},
                    lang,
                    currency_mode=context.user_data.get("currency_view", currency_mode),
                )
                return
            if state_name in {"month", "summary"}:
                await ReportHandler.handle_summary(
                    query,
                    user_id,
                    {"period": "month"},
                    lang,
                    currency_mode=context.user_data.get("currency_view", currency_mode),
                )
                return
            if state_name == "recent_transactions":
                await MenuService.send_recent_transactions(
                    query.message,
                    user_id,
                    lang,
                    currency_mode=context.user_data.get("currency_view", currency_mode),
                )
                return
            if state_name.startswith("balance") or state_name.startswith("fx_"):
                current_currency = context.user_data.get("currency_view", currency_mode)
                if state_name.endswith("_USD"):
                    current_currency = "USD"
                elif state_name.endswith("_KHR"):
                    current_currency = "KHR"
                await ReportHandler.handle_balance_currency(
                    query, user_id, lang, current_currency
                )
                return
            await MenuService.send_main_menu(query.message, user_name, user_id, lang)

        # ---------------------------------------------------------------- #
        # Action dispatch                                                   #
        # ---------------------------------------------------------------- #

        if action == "hide_all_buttons":
            # Treat hide-all as a one-step back from the all-buttons view.
            nav = current_state(context)
            if nav and nav.get("state") == "all_buttons":
                await on_back(update, context)
            nav = current_state(context)
            await _render_state(nav["state"] if nav else "main")
            return

        if action == "show_all_buttons":
            nav = current_state(context)
            # Push once; repeated taps should not stack duplicate all_buttons states.
            if not nav or nav.get("state") != "all_buttons":
                await on_next(update, context, "all_buttons")
            await _render_state("all_buttons")
            return

        if action == "quick_home_all":
            context.user_data["nav_stack"] = [
                {"state": "main", "data": {}},
                {"state": "all_buttons", "data": {}},
            ]
            await _render_state("all_buttons")
            return

        if action == "quick_balance":
            await on_next(update, context, "balance")
            await ReportHandler.handle_balance_currency(query, user_id, lang, currency_mode)
            return

        if action == "quick_today":
            await on_next(update, context, "today")
            await ReportHandler.handle_summary(
                query, user_id, {"period": "day"}, lang, currency_mode=currency_mode
            )
            return

        if action == "quick_month":
            await on_next(update, context, "month")
            await ReportHandler.handle_summary(
                query, user_id, {"period": "month"}, lang, currency_mode=currency_mode
            )
            return

        if action == "quick_summary":
            await on_next(update, context, "summary")
            await ReportHandler.handle_summary(
                query, user_id, {"period": "month"}, lang, currency_mode=currency_mode
            )
            return

        if action == "quick_balance_toggle":
            next_currency = "KHR" if currency_mode == "USD" else "USD"
            context.user_data["currency_view"] = next_currency
            await on_next(update, context, f"balance_{next_currency}")
            await ReportHandler.handle_balance_currency(query, user_id, lang, next_currency)
            return

        if action == "quick_balance_usd":
            context.user_data["currency_view"] = "USD"
            await on_next(update, context, "balance_usd")
            await ReportHandler.handle_balance_currency(query, user_id, lang, "USD")
            return

        if action == "quick_balance_khr":
            context.user_data["currency_view"] = "KHR"
            await on_next(update, context, "balance_khr")
            await ReportHandler.handle_balance_currency(query, user_id, lang, "KHR")
            return

        if action == "quick_fx":
            next_currency = "KHR" if currency_mode == "USD" else "USD"
            context.user_data["currency_view"] = next_currency
            nav = current_state(context)
            current = (nav or {}).get("state", "")
            if current in {"today", "month", "summary"}:
                await on_next(update, context, current)
                period = "day" if current == "today" else "month"
                await ReportHandler.handle_summary(
                    query,
                    user_id,
                    {"period": period},
                    lang,
                    currency_mode=next_currency,
                )
            else:
                await on_next(update, context, f"fx_{next_currency}")
                await ReportHandler.handle_balance_currency(query, user_id, lang, next_currency)
            return

        if action == "quick_list":
            await on_next(update, context, "recent_transactions")
            await MenuService.send_recent_transactions(
                query.message, user_id, lang, currency_mode=currency_mode
            )
            return

        if action == "quick_add_expense":
            await on_next(update, context, "add_expense")
            await _render_state("add_expense")
            return

        if action == "quick_add_income":
            await on_next(update, context, "add_income")
            await _render_state("add_income")
            return

        if action == "quick_help":
            await on_next(update, context, "help")
            help_support_rows = build_help_support_rows(
                lang, context.user_data.get("nav_stack", [])
            )
            await MenuService.reply_with_menu(
                query.message,
                _usage_instructions(lang),
                lang=lang,
                parse_mode=ParseMode.HTML,
                extra_rows=help_support_rows,
            )
            return

        if action == "quick_back_main":
            await on_back(update, context)
            nav = current_state(context)
            await _render_state(nav["state"] if nav else "main")
            return

        if action == "quick_lang_kh":
            context.user_data["lang"] = LANG_KH
            context.user_data["nav_stack"] = [{"state": "main", "data": {}}]
            await MenuService.send_main_menu(query.message, user_name, user_id, LANG_KH)
            return

        if action == "quick_lang_en":
            context.user_data["lang"] = LANG_EN
            context.user_data["nav_stack"] = [{"state": "main", "data": {}}]
            await MenuService.send_main_menu(query.message, user_name, user_id, LANG_EN)
            return

        if action in {"help_user_guide", "usage_instructions"}:
            await on_next(update, context, "usage_instructions")
            nav_stack = context.user_data.get("nav_stack", [])
            extra_rows = []
            if len(nav_stack) > 1:
                extra_rows = [
                    [
                        make_callback_button(
                            _t(lang, f"{_icon('back')} ត្រឡប់ក្រោយ", f"{_icon('back')} Back"),
                            "quick_back_main",
                        )
                    ]
                ]
            await MenuService.reply_with_menu(
                query.message,
                _usage_instructions(lang),
                lang=lang,
                parse_mode=ParseMode.HTML,
                extra_rows=extra_rows,
            )
            return

        # Fallback for unknown actions
        nav_stack = context.user_data.get("nav_stack", [])
        extra_rows = []
        if len(nav_stack) > 1:
            extra_rows = [
                [
                    make_callback_button(
                        _t(lang, f"{_icon('back')} ត្រឡប់ក្រោយ", f"{_icon('back')} Back"),
                        "quick_back_main",
                    )
                ]
            ]
        await MenuService.reply_with_menu(
            query.message,
            _t(
                lang,
                f"{_icon('info')} ប៊ូតុងនេះមិនទាន់អាចប្រើបានទេ។ សូមព្យាយាមម្ដងទៀត។",
                f"{_icon('info')} This action is not available right now. Please try again.",
            ),
            lang=lang,
            extra_rows=extra_rows,
        )


# Module-level shortcut for registering with ApplicationBuilder
handle_quick_action = CallbackHandler.handle_quick_action
