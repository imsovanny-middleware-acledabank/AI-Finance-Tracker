"""Menu service — reply helpers and menu-sending functions."""
import asyncio
import html
import os
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ParseMode

from .bot_ui import BotUI
from .buttons import (
    _all_buttons_extra_rows as btn_all_buttons_extra_rows,
    _base_menu_rows as btn_base_menu_rows,
    _entry_extra_rows as btn_entry_extra_rows,
    _help_extra_rows as btn_help_extra_rows,
    _report_extra_rows as btn_report_extra_rows,
    build_help_support_rows,
    make_callback_button,
)
from .ui_texts import BotUITexts

LANG_EN = BotUI.LANG_EN
LANG_KH = BotUI.LANG_KH
ICONS = BotUI.ICONS


def _t(lang: str, kh_text: str, en_text: str) -> str:
    return BotUI.t(lang, kh_text, en_text)


def _icon(name: str, **kwargs) -> str:
    return BotUI.icon(name, **kwargs)


def _sanitize_text_icons(text, keep_warning: bool = True) -> str:
    return BotUI.sanitize_text_icons(text, keep_warning=keep_warning)


def _receipt_divider() -> str:
    return BotUI.receipt_divider()


def _receipt_hd() -> str:
    return BotUI.receipt_header_divider()


def _to_plain_text_for_receipt(text: str, parse_mode=None) -> str:
    raw = "" if text is None else str(text)
    if parse_mode == ParseMode.HTML:
        # Keep user-provided HTML as-is for rich formatting support.
        return raw

    # For markdown/plain text, normalize into clean plain text before HTML wrapping.
    cleaned = raw
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
    cleaned = re.sub(r"[`*_~]", "", cleaned)
    return html.escape(cleaned)


def _ensure_full_receipt(text: str, lang: str, parse_mode=None) -> str:
    body = _to_plain_text_for_receipt(text, parse_mode=parse_mode).strip()
    if not body:
        body = _t(lang, "មិនមានទិន្នន័យ", "No data")

    # If already rendered as full receipt, keep it unchanged.
    if "<blockquote>" in body:
        return body

    title = _t(lang, "បង្កាន់ដៃ", "Receipt")
    return (
        f"<b>{title}</b>\n"
        f"<blockquote>{body}</blockquote>"
    )


class MenuService:
    """Builds keyboards and sends menus / reply messages."""

    # ------------------------------------------------------------------ #
    # URL helpers                                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def public_app_url() -> str:
        explicit = (os.getenv("APP_PUBLIC_URL") or "").strip().rstrip("/")
        if explicit:
            if not explicit.startswith(("http://", "https://")):
                explicit = f"https://{explicit.lstrip('/')}"
            return explicit
        domain = (os.getenv("TELEGRAM_WIDGET_DOMAIN") or "").strip().lower().strip("/")
        if domain and not domain.startswith(("http://", "https://")):
            return f"https://{domain}"
        return domain

    @classmethod
    def public_login_url(cls) -> str:
        base = cls.public_app_url().rstrip("/")
        return f"{base}/login/?next=/" if base else ""

    # ------------------------------------------------------------------ #
    # Row / keyboard builders                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def base_menu_rows(
        cls, lang: str, include_show_all: bool = True, include_lang: bool = True
    ):
        return btn_base_menu_rows(
            lang,
            include_show_all=include_show_all,
            include_lang=include_lang,
            _public_login_url=cls.public_login_url,
            _t=_t,
            _icon=_icon,
            ICONS=ICONS,
            InlineKeyboardButton=InlineKeyboardButton,
            WebAppInfo=WebAppInfo,
        )

    @classmethod
    def entry_extra_rows(cls, lang: str):
        return btn_entry_extra_rows(lang, _t=_t, _icon=_icon)

    @classmethod
    def report_extra_rows(cls, lang: str, currency_mode: str = "USD"):
        return btn_report_extra_rows(lang, currency_mode=currency_mode, _t=_t, _icon=_icon)

    @classmethod
    def help_extra_rows(cls, lang: str, currency_mode: str = "USD"):
        return btn_help_extra_rows(lang, currency_mode=currency_mode, _t=_t, _icon=_icon)

    @classmethod
    def all_buttons_extra_rows(cls, lang: str):
        return btn_all_buttons_extra_rows(lang, _t=_t, _icon=_icon, ICONS=ICONS)

    @classmethod
    def build_start_keyboard(
        cls, lang: str, extra_rows=None
    ) -> InlineKeyboardMarkup | None:
        if extra_rows:
            rows = cls.base_menu_rows(lang, include_show_all=False, include_lang=False) + [
                r for r in extra_rows if r
            ]
        else:
            rows = cls.base_menu_rows(lang, include_show_all=True, include_lang=True)
        return InlineKeyboardMarkup(rows) if rows else None

    @classmethod
    def reply_options(cls, **kwargs):
        lang = kwargs.pop("lang", LANG_EN)
        extra_rows = kwargs.pop("extra_rows", None)
        options = dict(kwargs)
        options.setdefault(
            "reply_markup", cls.build_start_keyboard(lang=lang, extra_rows=extra_rows)
        )
        return options

    # ------------------------------------------------------------------ #
    # Text helpers                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def normalize_currency_mode(mode: str | None) -> str:
        m = (mode or "USD").upper()
        return m if m in ("USD", "KHR") else "USD"

    @staticmethod
    def start_help_text(lang: str, user_name: str, user_id: int, app_url: str) -> str:
        return BotUITexts.start_help_text(lang, user_name, user_id, app_url, LANG_KH)

    # ------------------------------------------------------------------ #
    # Send helpers                                                         #
    # ------------------------------------------------------------------ #

    @classmethod
    async def reply_with_menu(cls, message, text: str, lang: str = LANG_EN, **kwargs):
        if message is None:
            return None
        parse_mode = kwargs.pop("parse_mode", None)
        safe_text = _sanitize_text_icons(text, keep_warning=True)
        return await message.reply_text(
            safe_text,
            **cls.reply_options(lang=lang, parse_mode=parse_mode, **kwargs),
        )

    @classmethod
    async def send_with_menu(
        cls, bot, chat_id: int, text: str, lang: str = LANG_EN, **kwargs
    ):
        parse_mode = kwargs.pop("parse_mode", None)
        safe_text = _sanitize_text_icons(text, keep_warning=True)
        return await bot.send_message(
            chat_id=chat_id,
            text=safe_text,
            **cls.reply_options(lang=lang, parse_mode=parse_mode, **kwargs),
        )

    @classmethod
    async def send_main_menu(cls, message, user_name: str, user_id: int, lang: str):
        """Send the top-level welcome/main menu."""
        await cls.reply_with_menu(
            message,
            cls.start_help_text(lang, user_name, user_id, cls.public_app_url()),
            lang=lang,
            parse_mode=ParseMode.HTML,
            extra_rows=None,
        )

    @classmethod
    async def send_help_message(
        cls, message, user_name: str, user_id: int, lang: str, currency_mode: str = "USD"
    ):
        await cls.reply_with_menu(
            message,
            cls.start_help_text(lang, user_name, user_id, cls.public_app_url()),
            lang=lang,
            parse_mode=ParseMode.HTML,
            extra_rows=cls.help_extra_rows(lang, currency_mode=currency_mode),
        )

    @classmethod
    async def send_recent_transactions(
        cls, message, user_id: int, lang: str, currency_mode: str = "USD"
    ):
        from tracker.models import Transaction

        def fetch_list():
            return list(
                Transaction.objects.filter(
                    telegram_id=user_id,
                    transaction_type__in=["income", "expense"],
                )
                .order_by("-transaction_date", "-created_at")[:10]
            )

        transactions = await asyncio.to_thread(fetch_list)
        if not transactions:
            await cls.reply_with_menu(
                message,
                _t(
                    lang,
                    f"{_icon('recent')} មិនទាន់មានប្រតិបត្តិការនៅឡើយទេ។",
                    f"{_icon('recent')} No transactions recorded yet.",
                ),
                lang=lang,
                extra_rows=cls.report_extra_rows(lang, currency_mode=currency_mode),
            )
            return

        lines = [
            _t(
                lang,
                f"{_icon('recent')} *ប្រតិបត្តិការថ្មីៗ (10 ចុងក្រោយ — ចំណូល + ចំណាយ)*",
                f"{_icon('recent')} *Recent Transactions (last 10 — income + expense)*",
            )
        ]
        for tx in transactions:
            tx_type_label = _t(
                lang,
                "ចំណូល" if tx.transaction_type == "income" else "ចំណាយ",
                "Income" if tx.transaction_type == "income" else "Expense",
            )
            cur = getattr(tx, "currency", "USD") or "USD"
            sym = "$" if cur == "USD" else "៛"
            note = tx.note or _t(lang, "មិនមាន", "N/A")
            lines.append(
                f"{tx.transaction_date} | {tx_type_label} | {sym}{tx.amount:,.2f} ({cur}) - {tx.category_name or tx.category} - {note}"
            )

        await cls.reply_with_menu(
            message,
            "\n".join(lines),
            lang=lang,
            parse_mode=ParseMode.MARKDOWN,
            extra_rows=cls.report_extra_rows(lang, currency_mode=currency_mode),
        )

    @classmethod
    async def send_quick_entry_help(cls, message, entry_type: str, lang: str):
        if entry_type == "expense":
            text = _t(
                lang,
                f"{_icon('add')} <b>របៀបបន្ថែមចំណាយ</b>\n\nសាកផ្ញើសារដូចខាងក្រោម៖\n• <code>ចំណាយ $5 អាហារ</code>\n• <code>ចំណាយ 20000៛ ធ្វើដំណើរ</code>\n• <code>ចំណាយ $12 កាហ្វេ</code>\n\n<blockquote>សរសេរជាប្រយោគធម្មតាក៏បាន — bot នឹងជួយយល់ឲ្យ។</blockquote>\n<tg-spoiler>Tip: អាចភ្ជាប់ note នៅខាងចុងសារ</tg-spoiler>",
                f"{_icon('add')} <b>How to add expense</b>\n\nTry sending messages like:\n• <code>spent $5 on food</code>\n• <code>spent $12 on coffee</code>\n• <code>spent 20000 KHR on transport</code>\n\n<blockquote>You can write naturally — the bot will understand.</blockquote>\n<tg-spoiler>Tip: You can append a note at the end.</tg-spoiler>",
            )
        else:
            text = _t(
                lang,
                f"{_icon('add')} <b>របៀបបន្ថែមចំណូល</b>\n\nសាកផ្ញើសារដូចខាងក្រោម៖\n• <code>ចំណូល $100 ប្រាក់ខែ</code>\n• <code>បាន 40000៛ ពីលក់ទំនិញ</code>\n• <code>ចំណូល $50 ការងារក្រៅម៉ោង</code>\n\n<blockquote>សរសេរជាប្រយោគធម្មតាក៏បាន — bot នឹងជួយយល់ឲ្យ។</blockquote>\n<tg-spoiler>Tip: អាចបញ្ជាក់ប្រភេទចំណូលឲ្យកាន់តែច្បាស់</tg-spoiler>",
                f"{_icon('add')} <b>How to add income</b>\n\nTry sending messages like:\n• <code>earned $100 salary</code>\n• <code>earned $50 freelance</code>\n• <code>received 40000 KHR from sales</code>\n\n<blockquote>You can write naturally — the bot will understand.</blockquote>\n<tg-spoiler>Tip: Add income source for better categorization.</tg-spoiler>",
            )

        await cls.reply_with_menu(
            message,
            text,
            lang=lang,
            parse_mode=ParseMode.HTML,
            extra_rows=cls.entry_extra_rows(lang),
        )
