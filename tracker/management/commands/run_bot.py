"""Telegram bot command for the finance tracker app."""


# --- Utility functions needed everywhere ---
def _fmt(val):
    """Format a Decimal or number for display."""
    try:
        return f"${val:,.2f}" if isinstance(val, (float, Decimal)) else str(val)
    except Exception:
        return str(val)


async def handle_balance_currency(update, user_id, lang, currency_mode):
    """Wrapper for handle_balance to match expected signature."""
    currency = currency_mode
    await handle_balance(update, user_id, lang, currency_mode=currency)


from decimal import Decimal, InvalidOperation

from dotenv import load_dotenv

load_dotenv()
import os

print("[DEBUG] EXCHANGERATE_API_KEY from env:", os.getenv("EXCHANGERATE_API_KEY"))
import asyncio
import html

USD_KHR_FALLBACK_RATE = Decimal("4012")
import re
from datetime import date as _date
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import Sum
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from tracker.models import Transaction
from tracker.services import analyze_finance_text, analyze_reply_action


async def cmd_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the current USD→KHR exchange rate from the API."""
    lang = _detect_user_lang(update, context)
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
    await reply_with_menu(update.message, msg, lang=lang)


def register_rate_command(app):
    app.add_handler(CommandHandler("rate", cmd_rate))


import time

import aiohttp

_EXCHANGE_RATE_CACHE = {
    "usd_to_khr": None,
    "timestamp": 0,
}


async def fetch_usd_to_khr_rate(force_refresh=False):
    """Fetch USD to KHR exchange rate from exchangerate-api.com, with fallback to default rate if API fails."""
    import json

    # Cache for 10 minutes
    CACHE_TTL = 600
    now = time.time()
    if (
        not force_refresh
        and _EXCHANGE_RATE_CACHE["usd_to_khr"]
        and (now - _EXCHANGE_RATE_CACHE["timestamp"] < CACHE_TTL)
    ):
        print("[DEBUG] Using cached rate:", _EXCHANGE_RATE_CACHE["usd_to_khr"])
        return _EXCHANGE_RATE_CACHE["usd_to_khr"]
    api_key = os.getenv("EXCHANGERATE_API_KEY", "6c907c135d5ef9e007ef3c83")
    url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
    try:
        print(f"[DEBUG] ExchangeRate API url: {url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                print(f"[DEBUG] ExchangeRate API status: {resp.status}")
                data = await resp.json()
                print(f"[DEBUG] ExchangeRate API raw response: {json.dumps(data)}")
                khr = data.get("conversion_rates", {}).get("KHR")
                print(f"[DEBUG] ExchangeRate API KHR: {khr}")
                if (
                    resp.status != 200
                    or khr is None
                    or not isinstance(khr, (int, float))
                ):
                    print(
                        f"[DEBUG] API call failed or invalid KHR rate, using fallback."
                    )
                    fallback_rate = USD_KHR_FALLBACK_RATE
                    _EXCHANGE_RATE_CACHE["usd_to_khr"] = fallback_rate
                    _EXCHANGE_RATE_CACHE["timestamp"] = now
                    return fallback_rate
                _EXCHANGE_RATE_CACHE["usd_to_khr"] = Decimal(str(khr))
                _EXCHANGE_RATE_CACHE["timestamp"] = now
                return Decimal(str(khr))
    except Exception as e:
        print(f"[DEBUG] ExchangeRate API error: {e}")
        fallback_rate = USD_KHR_FALLBACK_RATE
        _EXCHANGE_RATE_CACHE["usd_to_khr"] = fallback_rate
        _EXCHANGE_RATE_CACHE["timestamp"] = now
        return fallback_rate


def _usage_instructions(lang: str) -> str:
    if lang == LANG_KH:
        return (
            f"<b>របៀបប្រើប្រាស់កម្មវិធី</b>\n"
            f"\n"
            f"<b>I. ➕ បញ្ចូលចំណាយ/ចំណូល</b>\n"
            f"• ចុច <b>➕ បន្ថែមចំណាយ</b> ឬ <b>➕ បន្ថែមចំណូល</b>\n"
            f"• ឬសរសេរ៖ <code>ចំណាយ $5 អាហារ</code> ឬ <code>ចំណូល $100 ប្រាក់ខែ</code>\n"
            f"\n"
            f"<b>II. 💰 មើលសមតុល្យ និងរបាយការណ៍</b>\n"
            f"• ចុច <b>💰 សមតុល្យ</b> ដើម្បីមើលសមតុល្យ\n"
            f"• ចុច <b>📊 សរុប</b> ឬ <b>🗓 ខែនេះ</b> ដើម្បីមើលរបាយការណ៍\n"
            f"• ឬសរសេរ៖ <code>សមតុល្យ</code> ឬ <code>របាយការណ៍</code>\n"
            f"\n"
            f"<b>III. 🇰🇭 ប្តូរភាសា</b>\n"
            f"• ចុច <b>🇰🇭 Khmer</b> ឬ <b>🇺🇸 English</b> ដើម្បីប្ដូរភាសា\n"
            f"\n"
            f"<b>IV. 🛠️ បង្ហាញ/បិទប៊ូតុង</b>\n"
            f"• ចុច <b>Show All Buttons</b> ដើម្បីបង្ហាញប៊ូតុងទាំងអស់\n"
            f"• ចុច <b>Hide All Buttons</b> ដើម្បីបិទប៊ូតុង\n"
            f"\n"
            f"<b>V. ↩️ ត្រឡប់ក្រោយ</b>\n"
            f"• ចុច <b>⬅️ ត្រឡប់ក្រោយ</b> ដើម្បីត្រឡប់ទៅមុខងារមុន\n"
            f"\n"
            f"<b>VI. 💡 គន្លឹះបន្ថែម</b>\n"
            f"• អាចផ្ញើសារជាភាសាធម្មតា ឬប្រើប៊ូតុងសម្រាប់សកម្មភាពលឿន\n"
            f"• អាចបញ្ចូលសំឡេង ឬរូបភាព (AI នឹងជួយយល់)\n"
            f"\n"
            f"<i>មានសំណួរឬបញ្ហា? ចុច Help ឬទាក់ទង admin!</i>"
        )
    return (
        f"<b>How to Use the App</b>\n"
        f"\n"
        f"<b>I. ➕ Add Expense/Income</b>\n"
        f"• Tap <b>➕ Add Expense</b> or <b>➕ Add Income</b>\n"
        f"• Or type: <code>spent $5 on food</code> or <code>earned $100 salary</code>\n"
        f"\n"
        f"<b>II. 💰 View Balance & Reports</b>\n"
        f"• Tap <b>💰 Balance</b> to see your balance\n"
        f"• Tap <b>📊 Summary</b> or <b>🗓 This Month</b> for reports\n"
        f"• Or type: <code>balance</code> or <code>report</code>\n"
        f"\n"
        f"<b>III. 🇰🇭 Change Language</b>\n"
        f"• Tap <b>🇰🇭 Khmer</b> or <b>🇺🇸 English</b> to switch language\n"
        f"\n"
        f"<b>IV. 🛠️ Show/Hide Buttons</b>\n"
        f"• Tap <b>Show All Buttons</b> to show all quick actions\n"
        f"• Tap <b>Hide All Buttons</b> to hide them\n"
        f"\n"
        f"<b>V. ↩️ Back</b>\n"
        f"• Tap <b>⬅️ Back</b> to return to the previous menu\n"
        f"\n"
        f"<b>VI. 💡 Tips</b>\n"
        f"• You can type naturally or use the buttons for quick actions\n"
        f"• You can send voice or photo (AI will help understand)\n"
        f"\n"
        f"<i>Need help? Tap Help or contact admin!</i>"
    )


def _all_buttons_extra_rows(lang: str):
    # All main action buttons, including Summary and Recent, only once each, plus Hide All Buttons (no Show All Buttons, no duplicate language button)
    rows = [
        [
            _make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណាយ", f"{_icon('add')} Add Expense"),
                "quick_add_expense",
            ),
            _make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណូល", f"{_icon('add')} Add Income"),
                "quick_add_income",
            ),
        ],
        [
            _make_callback_button(
                _t(lang, f"{_icon('balance')} សមតុល្យ", f"{_icon('balance')} Balance"),
                "quick_balance",
            ),
            _make_callback_button(
                _t(lang, f"{_icon('today')} ថ្ងៃនេះ", f"{_icon('today')} Today"),
                "quick_today",
            ),
        ],
        [
            _make_callback_button(
                _t(lang, f"{_icon('month')} ខែនេះ", f"{_icon('month')} This Month"),
                "quick_month",
            ),
            _make_callback_button(
                _t(lang, f"{_icon('fx')} KHR", f"{_icon('fx')} USD"), "quick_fx"
            ),
        ],
        [
            _make_callback_button(
                _t(lang, f"{_icon('recent')} បញ្ជីថ្មីៗ", f"{_icon('recent')} Recent"),
                "quick_list",
            ),
            _make_callback_button(
                _t(lang, f"{_icon('summary')} សរុប", f"{_icon('summary')} Summary"),
                "quick_summary",
            ),
        ],
        [
            _make_callback_button(
                _t(lang, f"{_icon('help')} ជំនួយ", f"{_icon('help')} Help"), "quick_help"
            ),
        ],
        [
            _make_callback_button(
                _t(lang, "បិទប៊ូតុងទាំងអស់", "Hide All Buttons"), "hide_all_buttons"
            ),
        ],
    ]
    # Add language toggle button at the bottom
    if lang == LANG_KH:
        rows.append(
            [_make_callback_button(f"{ICONS['lang_en']} English", "quick_lang_en")]
        )
    else:
        rows.append(
            [_make_callback_button(f"{ICONS['lang_kh']} Khmer", "quick_lang_kh")]
        )
    return rows


import asyncio
import html

# tracker/management/commands/run_bot.py
import os
from datetime import date as _date
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db.models import Sum
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from tracker.models import Transaction
from tracker.services import analyze_finance_text, analyze_reply_action

load_dotenv()

import re

LANG_KH = "km"
LANG_EN = "en"

ICONS = {
    "open_app": "🚀",
    "balance": "💰",
    "today": "📅",
    "month": "🗓",
    "month_alt": "📅",
    "help": "❓",
    "lang_kh": "🇰🇭",
    "lang_en": "🇺🇸",
    "add": "➕",
    "recent": "📋",
    "summary": "📊",
    "bot": "🤖",
    "style": "🎨",
    "wave": "👋",
    "id": "🆔",
    "dashboard": "📊",
    "sparkles": "✨",
    "expense": "💸",
    "income": "💵",
    "khr": "💴",
    "category": "📂",
    "note": "📝",
    "calendar": "📆",
    "warning": "⚠️",
    "info": "ℹ️",
    "success": "✅",
    "error": "❌",
    "thinking": "🤖",
    "mic": "🎤",
    "camera": "📷",
    "document": "📄",
    "back": "↩️",
    "update": "🔄",
    "old": "📍",
    "new": "✨",
    "deficit": "📉",
    "tip": "💡",
    "question": "🤔",
    "fx": "💱",
    "net_positive": "🟢",
    "net_negative": "🔴",
}


def _icon(name: str, **kwargs) -> str:
    def _fmt(val):
        """Format a Decimal or number for display."""
        try:
            return f"${val:,.2f}" if isinstance(val, (float, Decimal)) else str(val)
        except Exception:
            return str(val)

    async def handle_balance_currency(update, user_id, lang, currency_mode):
        """Wrapper for handle_balance to match expected signature."""
        # currency_mode is passed in, so set currency variable accordingly
        currency = currency_mode
        await handle_balance(update, user_id, lang, currency_mode=currency)

    if name == "net":
        value = kwargs.get("value", Decimal("0"))
        try:
            value = Decimal(str(value))
        except Exception:
            value = Decimal("0")
        return ICONS["net_positive"] if value >= 0 else ICONS["net_negative"]
    if name == "tx_type":
        tx_type = (kwargs.get("tx_type") or "").lower()
        return ICONS["expense"] if tx_type == "expense" else ICONS["income"]
    return ICONS.get(name, "")


def _is_khmer_text(text: str | None) -> bool:
    if not text:
        return False
    khmer_chars = sum(1 for c in text if "\u1780" <= c <= "\u17FF")
    return khmer_chars > len(text) * 0.15


def _effective_user_from_any(update_like):
    if hasattr(update_like, "effective_user") and update_like.effective_user:
        return update_like.effective_user
    if hasattr(update_like, "from_user") and update_like.from_user:
        return update_like.from_user
    if hasattr(update_like, "message") and getattr(update_like, "message", None):
        return getattr(update_like.message, "from_user", None)
    return None


def _detect_user_lang(
    update_like=None,
    context: ContextTypes.DEFAULT_TYPE | None = None,
    text_hint: str | None = None,
) -> str:
    if _is_khmer_text(text_hint):
        lang = LANG_KH
    elif text_hint:
        lang = LANG_EN
    elif (
        context
        and getattr(context, "user_data", None)
        and context.user_data.get("lang") in (LANG_KH, LANG_EN)
    ):
        lang = context.user_data["lang"]
    else:
        user = _effective_user_from_any(update_like)
        code = ((getattr(user, "language_code", "") or "").lower()) if user else ""
        lang = LANG_KH if code.startswith("km") else LANG_EN

    if context and getattr(context, "user_data", None) is not None:
        context.user_data["lang"] = lang
    return lang


def _t(lang: str, kh: str, en: str) -> str:
    return kh if lang == LANG_KH else en


def _receipt_divider() -> str:
    return "────────────────────────"


def _sanitize_text_icons(text: str, keep_warning: bool = True) -> str:
    if not isinstance(text, str):
        return text

    warning_icon = ICONS.get("warning", "⚠️")
    placeholder = "__KEEP_WARNING_ICON__"
    value = text.replace(warning_icon, placeholder) if keep_warning else text

    # Remove most emoji/icon glyphs from normal text messages.
    value = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]", "", value)
    value = value.replace("\ufe0f", "")

    if keep_warning:
        value = value.replace(placeholder, warning_icon)

    # Clean spacing after icon removal.
    value = re.sub(r"[ \t]{2,}", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    return value.strip()


def _formatting_showcase(lang: str) -> str:
    if lang == LANG_KH:
        return (
            f"<b>{_icon('style')} រចនាប័ទ្មអត្ថបទ</b>\n"
            "• <b>ដិត (Bold)</b>\n"
            "• <i>ទ្រេត (Italic)</i>\n"
            "• <blockquote>Quote: ឧទាហរណ៍សម្រង់អត្ថបទ</blockquote>\n"
            "• <tg-spoiler>Tip សម្ងាត់: ចុចលើ spoiler ដើម្បីបង្ហាញ</tg-spoiler>\n"
        )

    return (
        f"<b>{_icon('style')} Text Formatting</b>\n"
        "• <b>Bold</b>\n"
        "• <i>Italic</i>\n"
        "• <blockquote>Quote: sample highlighted note</blockquote>\n"
        "• <tg-spoiler>Hidden tip: tap spoiler to reveal</tg-spoiler>\n"
    )


def _public_app_url() -> str:
    explicit = (os.getenv("APP_PUBLIC_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit

    domain = (os.getenv("TELEGRAM_WIDGET_DOMAIN") or "").strip().lower().strip("/")
    if domain and not domain.startswith(("http://", "https://")):
        return f"https://{domain}"
    return domain


def _public_login_url() -> str:
    base = _public_app_url().rstrip("/")
    if not base:
        return ""
    return f"{base}/login/?next=/"


def _make_callback_button(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=callback_data)


def _normalize_currency_mode(mode: str | None) -> str:
    m = (mode or "USD").upper()
    return m if m in ("USD", "KHR") else "USD"


def _base_menu_rows(
    lang: str, include_show_all: bool = True, include_lang: bool = True
):
    rows = []
    login_url = _public_login_url()
    if login_url:
        rows.append(
            [
                InlineKeyboardButton(
                    _t(
                        lang,
                        f"{_icon('open_app')} បើកកម្មវិធី",
                        f"{_icon('open_app')} Open App",
                    ),
                    web_app=WebAppInfo(url=login_url),
                )
            ]
        )
    if include_show_all:
        rows.append(
            [
                _make_callback_button(
                    _t(lang, "បង្ហាញប៊ូតុងទាំងអស់", "Show All Buttons"), "show_all_buttons"
                )
            ]
        )
    if include_lang:
        if lang == LANG_KH:
            rows.append(
                [_make_callback_button(f"{ICONS['lang_en']} English", "quick_lang_en")]
            )
        else:
            rows.append(
                [_make_callback_button(f"{ICONS['lang_kh']} Khmer", "quick_lang_kh")]
            )
    return rows


def _entry_extra_rows(lang: str):
    # Show all main action buttons, plus Back
    return [
        [
            _make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណាយ", f"{_icon('add')} Add Expense"),
                "quick_add_expense",
            ),
            _make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណូល", f"{_icon('add')} Add Income"),
                "quick_add_income",
            ),
        ],
        [
            _make_callback_button(_t(lang, "⬅️ ត្រឡប់ក្រោយ", "⬅️ Back"), "quick_back_main"),
        ],
    ]


def _report_extra_rows(lang: str, currency_mode: str = "USD"):
    # Show all main action buttons, plus Back
    return [
        [
            _make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណាយ", f"{_icon('add')} Add Expense"),
                "quick_add_expense",
            ),
            _make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណូល", f"{_icon('add')} Add Income"),
                "quick_add_income",
            ),
        ],
        [
            _make_callback_button(
                _t(lang, f"{_icon('recent')} បញ្ជីថ្មីៗ", f"{_icon('recent')} Recent"),
                "quick_list",
            ),
            _make_callback_button(
                _t(lang, f"{_icon('summary')} សរុប", f"{_icon('summary')} Summary"),
                "quick_summary",
            ),
        ],
        [
            _make_callback_button(_t(lang, "⬅️ ត្រឡប់ក្រោយ", "⬅️ Back"), "quick_back_main"),
        ],
    ]


def _help_extra_rows(lang: str, currency_mode: str = "USD"):
    # Help: show all main action buttons, no Back
    return [
        [
            _make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណាយ", f"{_icon('add')} Add Expense"),
                "quick_add_expense",
            ),
            _make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណូល", f"{_icon('add')} Add Income"),
                "quick_add_income",
            ),
        ],
        [
            _make_callback_button(
                _t(lang, f"{_icon('recent')} បញ្ជីថ្មីៗ", f"{_icon('recent')} Recent"),
                "quick_list",
            ),
            _make_callback_button(
                _t(lang, f"{_icon('summary')} សរុប", f"{_icon('summary')} Summary"),
                "quick_summary",
            ),
        ],
    ]


def _build_start_keyboard(lang: str, extra_rows=None) -> InlineKeyboardMarkup | None:
    # Only add Show All Buttons and language button in main menu, not in all buttons menu
    if extra_rows:
        rows = _base_menu_rows(lang, include_show_all=False, include_lang=False) + [
            r for r in extra_rows if r
        ]
    else:
        rows = _base_menu_rows(lang, include_show_all=True, include_lang=True)
    return InlineKeyboardMarkup(rows) if rows else None


def _reply_options(**kwargs):
    lang = kwargs.pop("lang", LANG_EN)
    extra_rows = kwargs.pop("extra_rows", None)
    options = dict(kwargs)
    options.setdefault(
        "reply_markup", _build_start_keyboard(lang=lang, extra_rows=extra_rows)
    )
    return options


async def reply_with_menu(message, text, lang: str = LANG_EN, **kwargs):
    if message is None:
        return None
    safe_text = _sanitize_text_icons(text, keep_warning=True)
    return await message.reply_text(safe_text, **_reply_options(lang=lang, **kwargs))


async def send_with_menu(bot, chat_id: int, text: str, lang: str = LANG_EN, **kwargs):
    safe_text = _sanitize_text_icons(text, keep_warning=True)
    return await bot.send_message(
        chat_id=chat_id, text=safe_text, **_reply_options(lang=lang, **kwargs)
    )


def _start_help_text(lang: str, user_name: str, user_id: int, app_url: str) -> str:
    safe_name = html.escape(user_name)
    if lang == LANG_KH:
        return (
            f"<b>សួស្តី {safe_name}</b>\n\n"
            f"<b>អត្ថប្រយោជន៍សំខាន់ៗ</b>\n"
            f"• កត់ត្រាចំណូល/ចំណាយបានលឿន\n"
            f"• មើលសមតុល្យ និងរបាយការណ៍បានភ្លាមៗ\n"
            f"• AI ជួយចាត់ថ្នាក់ចំណាយដោយស្វ័យប្រវត្តិ\n"
            f"• ព្យាករណ៍ការចំណាយ និងផ្តល់អនុសាសន៍សន្សំប្រាក់\n"
            f"• ផ្តល់របាយការណ៍ និងសេចក្តីសង្ខេបប្រចាំខែជាភាសាខ្មែរ និងអង់គ្លេស\n"
            f"• មានសុវត្ថិភាពខ្ពស់ ដោយប្រើការអ៊ិនគ្រីបទិន្នន័យ\n\n"
            f"<b>របៀបប្រើប្រាស់</b>\n"
            f"• ផ្ញើសារចំណាយ ឬ ចំណូលដោយភាសាធម្មតា\n"
            f"• អាចសួរអំពីសមតុល្យ ឬរបាយការណ៍ប្រចាំខែ\n\n"
            f"អាចសរសេរ និយាយ ឬបញ្ចូលរូបភាព ឯកសារ (upload) បាន។\n"
            f"Tip: ចុចប៊ូតុងខាងក្រោម ដើម្បីប្រើបានលឿន។"
        )

    return (
        f"<b>Hello {safe_name}</b>\n\n"
        f"<b>Key Benefits</b>\n"
        f"• Quickly record income/expenses\n"
        f"• Instantly view balance and reports\n"
        f"• AI auto-categorizes your spending\n"
        f"• Predicts expenses & gives saving tips\n"
        f"• Monthly reports and summaries in Khmer & English\n"
        f"• High security with encrypted data\n\n"
        f"<b>How to use</b>\n"
        f"• Send income/expense in natural language\n"
        f"• Ask for balance or monthly report\n\n"
        f"You can type, speak, or upload images/docs.\n"
        f"Tip: Tap the buttons below for faster actions."
    )


async def send_help_message(
    message, user_name: str, user_id: int, lang: str, currency_mode: str = "USD"
):
    await reply_with_menu(
        message,
        _start_help_text(lang, user_name, user_id, _public_app_url()),
        lang=lang,
        parse_mode=ParseMode.HTML,
        extra_rows=_help_extra_rows(lang, currency_mode=currency_mode),
    )


async def send_main_menu(message, user_name: str, user_id: int, lang: str):
    """Return user to top-level menu (no function-specific extra rows)."""
    await reply_with_menu(
        message,
        _start_help_text(lang, user_name, user_id, _public_app_url()),
        lang=lang,
        parse_mode=ParseMode.HTML,
        extra_rows=None,  # Force no extra rows in main menu
    )


async def send_recent_transactions(
    message, user_id: int, lang: str, currency_mode: str = "USD"
):
    def fetch_list():
        return list(
            Transaction.objects.filter(telegram_id=user_id).order_by(
                "-transaction_date"
            )[:10]
        )

    transactions = await asyncio.to_thread(fetch_list)
    if not transactions:
        await reply_with_menu(
            message,
            _t(
                lang,
                f"{_icon('recent')} មិនទាន់មានប្រតិបត្តិការនៅឡើយទេ។",
                f"{_icon('recent')} No transactions recorded yet.",
            ),
            lang=lang,
            extra_rows=_report_extra_rows(lang, currency_mode=currency_mode),
        )
        return

    lines = [
        _t(
            lang,
            f"{_icon('recent')} *ប្រតិបត្តិការថ្មីៗ (10 ចុងក្រោយ)*",
            f"{_icon('recent')} *Recent Transactions (last 10)*",
        )
    ]
    for tx in transactions:
        icon = _icon("tx_type", tx_type=tx.transaction_type)
        cur = getattr(tx, "currency", "USD") or "USD"
        sym = "$" if cur == "USD" else "៛"
        note = tx.note or _t(lang, "មិនមាន", "N/A")
        lines.append(
            f"{icon} {tx.transaction_date}: {sym}{tx.amount:,.2f} ({cur}) - {tx.category_name or tx.category} - {note}"
        )

    await reply_with_menu(
        message,
        "\n".join(lines),
        lang=lang,
        parse_mode=ParseMode.MARKDOWN,
        extra_rows=_report_extra_rows(lang, currency_mode=currency_mode),
    )


async def send_quick_entry_help(message, entry_type: str, lang: str):
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

    await reply_with_menu(
        message,
        text,
        lang=lang,
        parse_mode=ParseMode.HTML,
        extra_rows=_entry_extra_rows(lang),
    )


async def handle_quick_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    # --- Menu stack helpers must be defined before use ---
    def push_menu(menu_name, args=None):
        stack = context.user_data.get("menu_stack", [])
        stack.append((menu_name, args or {}))
        context.user_data["menu_stack"] = stack

    def pop_menu():
        stack = context.user_data.get("menu_stack", [])
        if stack:
            stack.pop()
            context.user_data["menu_stack"] = stack
        return stack[-1] if stack else None

    await query.answer()

    action = query.data or ""
    user_id = query.from_user.id
    user = query.from_user
    user_name = user.first_name or ""
    if user.last_name:
        user_name = f"{user_name} {user.last_name}".strip()
    if not user_name.strip():
        user_name = "User"
    lang = _detect_user_lang(update, context)
    currency_mode = _normalize_currency_mode(context.user_data.get("currency_view"))
    context.user_data["currency_view"] = currency_mode

    if action == "hide_all_buttons":
        # Return to minimal main menu (Open App & Show All Buttons), with help text
        await reply_with_menu(
            query.message,
            _start_help_text(lang, user_name, user_id, _public_app_url()),
            lang=lang,
            parse_mode=ParseMode.HTML,
        )
        return

    if action == "show_all_buttons":
        # Show all main buttons, with help text
        await reply_with_menu(
            query.message,
            _start_help_text(lang, user_name, user_id, _public_app_url()),
            lang=lang,
            parse_mode=ParseMode.HTML,
            extra_rows=_all_buttons_extra_rows(lang),
        )
        return

    if action == "quick_balance":
        push_menu("all_buttons")
        await handle_balance_currency(query, user_id, lang, currency_mode)
        return
    if action == "quick_today":
        push_menu("all_buttons")
        await handle_summary(
            query, user_id, {"period": "day"}, lang, currency_mode=currency_mode
        )
        return
    if action == "quick_month":
        push_menu("all_buttons")
        await handle_summary(
            query, user_id, {"period": "month"}, lang, currency_mode=currency_mode
        )
        return
    if action == "quick_summary":
        push_menu("all_buttons")
        await handle_summary(
            query, user_id, {"period": "month"}, lang, currency_mode=currency_mode
        )
        return
    if action == "quick_balance_toggle":
        next_currency = "KHR" if currency_mode == "USD" else "USD"
        context.user_data["currency_view"] = next_currency
        push_menu("all_buttons")
        await handle_balance_currency(query, user_id, lang, next_currency)
        return
    if action == "quick_balance_usd":
        context.user_data["currency_view"] = "USD"
        push_menu("all_buttons")
        await handle_balance_currency(query, user_id, lang, "USD")
        return
    if action == "quick_balance_khr":
        context.user_data["currency_view"] = "KHR"
        push_menu("all_buttons")
        await handle_balance_currency(query, user_id, lang, "KHR")
        return
    if action == "quick_fx":
        # Toggle currency view (USD <-> KHR) and show balance in new currency
        next_currency = "KHR" if currency_mode == "USD" else "USD"
        context.user_data["currency_view"] = next_currency
        push_menu("all_buttons")
        await handle_balance_currency(query, user_id, lang, next_currency)
        return
    if action == "quick_list":
        push_menu("all_buttons")
        await send_recent_transactions(
            query.message, user_id, lang, currency_mode=currency_mode
        )
        return
    # Context-aware menu stack for back button
    menu_stack = context.user_data.get("menu_stack", [])

    def push_menu(menu_name, args=None):
        stack = context.user_data.get("menu_stack", [])
        stack.append((menu_name, args or {}))
        context.user_data["menu_stack"] = stack

    def pop_menu():
        stack = context.user_data.get("menu_stack", [])
        if stack:
            stack.pop()
            context.user_data["menu_stack"] = stack
        return stack[-1] if stack else None

    if action == "quick_add_expense":
        push_menu("add_expense")
        await send_quick_entry_help(query.message, "expense", lang)
        return
    if action == "quick_add_income":
        push_menu("add_income")
        await send_quick_entry_help(query.message, "income", lang)
        return
    if action == "quick_help":
        push_menu("help")
        # Custom help/support buttons
        help_support_rows = [
            [
                _make_callback_button(
                    _t(lang, "📞 ទាក់ទង Admin", "📞 Contact Admin"), "help_contact_admin"
                ),
                _make_callback_button(
                    _t(lang, "📖 របៀបប្រើប្រាស់", "📖 User Guide"), "help_user_guide"
                ),
            ],
            [
                _make_callback_button(_t(lang, "❓ សំណួរញឹកញាប់", "❓ FAQ"), "help_faq"),
                _make_callback_button(
                    _t(lang, "💬 ផ្ញើមតិយោបល់", "💬 Feedback"), "help_feedback"
                ),
            ],
            [
                _make_callback_button(
                    _t(lang, "⬅️ ត្រឡប់ក្រោយ", "⬅️ Back"), "quick_back_main"
                ),
            ],
        ]
        await reply_with_menu(
            query.message,
            _usage_instructions(lang),
            lang=lang,
            parse_mode=ParseMode.HTML,
            extra_rows=help_support_rows,
        )
        return
    if action == "quick_back_main":
        prev = pop_menu()
        if prev:
            menu, args = prev
            if menu == "main":
                await send_main_menu(query.message, user_name, user_id, lang)
            elif menu == "help":
                await send_help_message(
                    query.message, user_name, user_id, lang, currency_mode=currency_mode
                )
            elif menu == "add_expense":
                await send_quick_entry_help(query.message, "expense", lang)
            elif menu == "add_income":
                await send_quick_entry_help(query.message, "income", lang)
            elif menu == "all_buttons":
                await reply_with_menu(
                    query.message,
                    _start_help_text(lang, user_name, user_id, _public_app_url()),
                    lang=lang,
                    parse_mode=ParseMode.HTML,
                    extra_rows=_all_buttons_extra_rows(lang),
                )
            elif menu == "usage_instructions":
                await reply_with_menu(
                    query.message,
                    _usage_instructions(lang),
                    lang=lang,
                    parse_mode=ParseMode.HTML,
                    extra_rows=[
                        [
                            _make_callback_button(
                                _t(lang, "⬅️ ត្រឡប់ក្រោយ", "⬅️ Back"), "quick_back_main"
                            )
                        ]
                    ],
                )
            # Add more menu types as needed
            else:
                await send_main_menu(query.message, user_name, user_id, lang)
        else:
            await send_main_menu(query.message, user_name, user_id, lang)
        return
    if action == "quick_lang_kh":
        context.user_data["lang"] = LANG_KH
        await send_main_menu(query.message, user_name, user_id, LANG_KH)
        return
    if action == "quick_lang_en":
        context.user_data["lang"] = LANG_EN
        await send_main_menu(query.message, user_name, user_id, LANG_EN)
        return

    # Show usage instructions if the button is for usage/help
    if action == "help_user_guide" or action == "usage_instructions":
        push_menu("usage_instructions")
        await reply_with_menu(
            query.message,
            _usage_instructions(lang),
            lang=lang,
            parse_mode=ParseMode.HTML,
            extra_rows=[
                [
                    _make_callback_button(
                        _t(lang, "⬅️ ត្រឡប់ក្រោយ", "⬅️ Back"), "quick_back_main"
                    )
                ]
            ],
        )
        return
    await reply_with_menu(
        query.message,
        _t(
            lang,
            f"{_icon('info')} ប៊ូតុងនេះមិនទាន់អាចប្រើបានទេ។ សូមព្យាយាមម្ដងទៀត។",
            f"{_icon('info')} This action is not available right now. Please try again.",
        ),
        lang=lang,
        extra_rows=[
            [_make_callback_button(_t(lang, "⬅️ ត្រឡប់ក្រោយ", "⬅️ Back"), "quick_back_main")]
        ],
    )


async def handle_reply_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reply to a transaction confirmation message — edit or delete via AI."""
    lang = _detect_user_lang(
        update, context, update.message.text if update and update.message else None
    )
    user_id = update.message.from_user.id
    reply_text = update.message.text
    original_msg = update.message.reply_to_message.text or ""

    # Extract transaction ID from original message (e.g., "#123")
    id_match = re.search(r"#(\d+)", original_msg)
    if not id_match:
        await reply_with_menu(
            update.message,
            _t(
                lang,
                f"{_icon('error')} រកមិនឃើញលេខសម្គាល់ប្រតិបត្តិការនៅក្នុងសារដើមទេ។",
                f"{_icon('error')} Cannot find transaction ID in the original message.",
            ),
            lang=lang,
        )
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
        await reply_with_menu(
            update.message,
            _t(
                lang,
                f"{_icon('error')} រកមិនឃើញប្រតិបត្តិការ #{tx_id} ឬអ្នកគ្មានសិទ្ធិ។",
                f"{_icon('error')} Transaction #{tx_id} not found or unauthorized.",
            ),
            lang=lang,
        )
        return

    await reply_with_menu(
        update.message,
        _t(
            lang,
            f"{_icon('thinking')} កំពុងវិភាគសំណើរបស់អ្នក...",
            f"{_icon('thinking')} Analyzing your request...",
        ),
        lang=lang,
    )

    try:
        # Ask AI what the user wants to do
        action_data = await asyncio.to_thread(
            analyze_reply_action, reply_text, original_msg
        )

        if not isinstance(action_data, dict):
            raise ValueError("AI response was not a JSON object")

        action = action_data.get("action", "unknown")

        if action == "delete":
            # Delete the transaction
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
            icon = _icon("tx_type", tx_type=info["type"])
            response = (
                f"{_icon('success')} *Transaction #{tx_id} Deleted*\n"
                f"{icon} {info['type'].capitalize()}: ${info['amount']:.2f}\n"
                f"{_icon('category')} {info['category']} | {_icon('today')} {info['date']}"
            )
            await reply_with_menu(
                update.message,
                response,
                lang=lang,
                parse_mode=ParseMode.MARKDOWN,
                extra_rows=_entry_extra_rows(lang),
            )

        elif action == "edit":
            changes = action_data.get("changes", {})
            if not any(v is not None for v in changes.values()):
                await reply_with_menu(
                    update.message,
                    _t(
                        lang,
                        f"{_icon('info')} មិនឃើញការកែប្រែថ្មីទេ។ សូមបញ្ជាក់អ្វីដែលចង់កែ។",
                        f"{_icon('info')} No changes detected. Please specify what to edit.",
                    ),
                    lang=lang,
                    extra_rows=_entry_extra_rows(lang),
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
                    import asyncio

                    rate = asyncio.run(fetch_usd_to_khr_rate())
                    if cur == "USD":
                        tx.amount_usd = new_amt
                        tx.amount_khr = new_amt * rate
                    else:
                        tx.amount_khr = new_amt
                        tx.amount_usd = (
                            new_amt / rate if rate else new_amt / rate
                        )  # Always use the latest rate, fallback handled in fetch_usd_to_khr_rate
                    updated_fields.append(
                        _t(
                            lang,
                            f"{_icon('balance')} ចំនួន: ${old:.2f} → ${float(new_amt):.2f}",
                            f"{_icon('balance')} Amount: ${old:.2f} → ${float(new_amt):.2f}",
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
                            f"{_icon('category')} ប្រភេទ: {old_cat} → {cat_obj.name}",
                            f"{_icon('category')} Category: {old_cat} → {cat_obj.name}",
                        )
                    )

                if changes.get("date") is not None:
                    old_date = tx.transaction_date.isoformat()
                    tx.transaction_date = _date.fromisoformat(changes["date"])
                    updated_fields.append(
                        _t(
                            lang,
                            f"{_icon('today')} កាលបរិច្ឆេទ: {old_date} → {changes['date']}",
                            f"{_icon('today')} Date: {old_date} → {changes['date']}",
                        )
                    )

                if changes.get("note") is not None:
                    old_note = tx.note or "(empty)"
                    tx.note = changes["note"]
                    updated_fields.append(
                        _t(
                            lang,
                            f"{_icon('note')} កំណត់សម្គាល់: {old_note} → {changes['note']}",
                            f"{_icon('note')} Note: {old_note} → {changes['note']}",
                        )
                    )

                tx.save()
                return updated_fields

            updated_fields = await asyncio.to_thread(apply_edits)
            lines = "\n".join(updated_fields)
            response = _t(
                lang,
                f"{_icon('success')} *បានកែប្រែប្រតិបត្តិការ #{tx_id}*\n\n{lines}",
                f"{_icon('success')} *Transaction #{tx_id} Updated*\n\n{lines}",
            )
            await reply_with_menu(
                update.message,
                response,
                lang=lang,
                parse_mode=ParseMode.MARKDOWN,
                extra_rows=_entry_extra_rows(lang),
            )

        else:
            msg = action_data.get("message", "I could not understand your request.")
            await reply_with_menu(
                update.message,
                f"{_icon('question')} {msg}\n\n"
                f"{_icon('tip')} *ណែនាំ:* ឆ្លើយតបដូចខាងក្រោម៖\n"
                f'• "delete" ឬ "លុប" ដើម្បីលុប\n'
                f'• "change amount to 50" ឬ "កែតម្លៃ 50" ដើម្បីកែ',
                parse_mode=ParseMode.MARKDOWN,
                lang=lang,
                extra_rows=_entry_extra_rows(lang),
            )

    except Exception as e:
        await reply_with_menu(
            update.message,
            _t(
                lang,
                f"{_icon('error')} មានបញ្ហា៖ {str(e)}",
                f"{_icon('error')} Error: {str(e)}",
            ),
            lang=lang,
            extra_rows=_entry_extra_rows(lang),
        )


async def handle_summary(
    update: Update, user_id, data, lang: str, currency_mode: str = "USD"
):
    """Generate a financial summary report for day/month/year."""
    message = update.message if getattr(update, "message", None) else update
    period = data.get("period", "month")
    target_date_str = data.get("date")

    try:
        target_date = (
            _date.fromisoformat(target_date_str) if target_date_str else _date.today()
        )
    except (ValueError, TypeError):
        target_date = _date.today()

    def fetch_summary():
        from django.db.models import Count, Q, Sum
        from django.db.models.functions import TruncDate, TruncMonth

        base_qs = Transaction.objects.filter(telegram_id=user_id)

        if period == "day":
            qs = base_qs.filter(transaction_date=target_date)
            label = f"{_icon('today')} {target_date.strftime('%d %b %Y')}"
            period_kh = "ប្រចាំថ្ងៃ"
        elif period == "year":
            qs = base_qs.filter(transaction_date__year=target_date.year)
            label = f"{_icon('today')} {target_date.year}"
            period_kh = "ប្រចាំឆ្នាំ"
        else:  # month
            qs = base_qs.filter(
                transaction_date__year=target_date.year,
                transaction_date__month=target_date.month,
            )
            label = f"{_icon('today')} {target_date.strftime('%b %Y')}"
            period_kh = "ប្រចាំខែ"

        income_usd = qs.filter(transaction_type="income").aggregate(
            t=Sum("amount_usd")
        )["t"] or Decimal("0")
        expense_usd = qs.filter(transaction_type="expense").aggregate(
            t=Sum("amount_usd")
        )["t"] or Decimal("0")
        income_count = qs.filter(transaction_type="income").count()
        expense_count = qs.filter(transaction_type="expense").count()
        net = income_usd - expense_usd

        # Top expense categories
        top_cats = (
            qs.filter(transaction_type="expense")
            .values("category_name")
            .annotate(total=Sum("amount_usd"), cnt=Count("id"))
            .order_by("-total")[:5]
        )

        # Daily breakdown for month/year
        daily_data = None
        if period in ("month", "year"):
            daily_data = list(
                qs.values("transaction_date")
                .annotate(
                    day_income=Sum("amount_usd", filter=Q(transaction_type="income")),
                    day_expense=Sum("amount_usd", filter=Q(transaction_type="expense")),
                )
                .order_by("-transaction_date")[:7]
            )

        # Overall all-time net (used for warning — not just period net)
        overall_income = base_qs.filter(transaction_type="income").aggregate(
            t=Sum("amount_usd")
        )["t"] or Decimal("0")
        overall_expense = base_qs.filter(transaction_type="expense").aggregate(
            t=Sum("amount_usd")
        )["t"] or Decimal("0")
        overall_net = overall_income - overall_expense

        return {
            "label": label,
            "period_kh": period_kh,
            "income_usd": income_usd,
            "expense_usd": expense_usd,
            "income_count": income_count,
            "expense_count": expense_count,
            "net": net,
            "overall_net": overall_net,
            "top_cats": list(top_cats),
            "daily_data": daily_data,
        }

    s = await asyncio.to_thread(fetch_summary)

    KHR = await fetch_usd_to_khr_rate()
    net_icon = _icon("net", value=s["net"])
    net_sign = "+" if s["net"] >= 0 else ""
    income_khr = s["income_usd"] * KHR
    expense_khr = s["expense_usd"] * KHR
    net_khr = s["net"] * KHR

    # Build category lines
    cat_lines = []
    if s["top_cats"]:
        for i, c in enumerate(s["top_cats"], 1):
            total = c["total"] or Decimal("0")
            cat_name = html.escape(str(c["category_name"]))
            cat_lines.append(
                f"{i}. <b>{cat_name}</b> — ${total:,.2f} | ៛{total * KHR:,.0f} ({c['cnt']}x)"
            )

    # Build daily breakdown
    daily_lines = []
    if s["daily_data"]:
        for d in s["daily_data"]:
            day = d["transaction_date"]
            d_inc = d["day_income"] or Decimal("0")
            d_exp = d["day_expense"] or Decimal("0")
            d_net = d_inc - d_exp
            d_icon = _icon("net", value=d_net)
            daily_lines.append(
                f"• <b>{day.strftime('%d %b')}</b>: +${d_inc:,.2f} -${d_exp:,.2f} {d_icon} ${d_net:,.2f}"
            )

    title = _t(
        lang,
        f"{_icon('summary')} របាយការណ៍{s['period_kh']}",
        f"{_icon('summary')} Financial Summary",
    )
    label_title = _t(lang, "រយៈពេល", "Period")
    usd_title = _t(
        lang, f"{_icon('income')} ផ្នែកដុល្លារ (USD)", f"{_icon('income')} USD Section"
    )
    khr_title = _t(lang, f"{_icon('khr')} ផ្នែករៀល (KHR)", f"{_icon('khr')} KHR Section")
    income_title = _t(lang, "ចំណូល", "Income")
    expense_title = _t(lang, "ចំណាយ", "Expenses")
    net_title = _t(lang, "នៅសល់", "Net Balance")
    tx_count_label = _t(lang, "ប្រតិបត្តិការ", "transactions")
    cat_title = _t(
        lang,
        f"{_icon('summary')} ចំណាយតាមប្រភេទ",
        f"{_icon('summary')} Expenses by Category",
    )
    days_title = _t(
        lang, f"{_icon('calendar')} ថ្ងៃថ្មីៗ", f"{_icon('calendar')} Recent Days"
    )

    response_parts = [
        f"<b>{title}</b>",
        _receipt_divider(),
        f"<blockquote>{label_title}: {html.escape(s['label'])}</blockquote>",
        "",
        f"<b>{usd_title}</b>",
        f"• {income_title}: ${s['income_usd']:,.2f}",
        f"• {expense_title}: ${s['expense_usd']:,.2f}",
        f"• {net_icon} {net_title}: {net_sign}${s['net']:,.2f}",
        "",
        _receipt_divider(),
        f"<b>{khr_title}</b>",
        f"• {income_title}: ៛{income_khr:,.0f}",
        f"• {expense_title}: ៛{expense_khr:,.0f}",
        f"• {net_icon} {net_title}: {net_sign}៛{net_khr:,.0f}",
        "",
        _receipt_divider(),
        f"{_icon('note')} <i>{s['income_count']} {tx_count_label} ({income_title}) • {s['expense_count']} {tx_count_label} ({expense_title})</i>",
    ]

    if cat_lines:
        response_parts.extend(["", f"<b>{cat_title}</b>", *cat_lines])

    if daily_lines:
        response_parts.extend(["", f"<b>{days_title}</b>", *daily_lines])

    if s["overall_net"] < 0:
        response_parts.extend(
            [
                "",
                _t(
                    lang,
                    f"<tg-spoiler>{_icon('warning')} ការព្រមាន៖ ចំណាយលើសចំណូល សូមពិចារណាកាត់បន្ថយចំណាយ។</tg-spoiler>",
                    f"<tg-spoiler>{_icon('warning')} Warning: Expenses exceed income. Consider reducing spending.</tg-spoiler>",
                ),
            ]
        )

    response = "\n".join(response_parts)

    await reply_with_menu(
        message,
        response,
        lang=lang,
        parse_mode=ParseMode.HTML,
        extra_rows=_report_extra_rows(lang, currency_mode=currency_mode),
    )


async def handle_balance(
    update: Update, user_id, lang: str, currency_mode: str = "USD"
):
    """Show the user's current balance: total income, total expenses, and remaining."""
    message = update.message if getattr(update, "message", None) else update

    KHR = await fetch_usd_to_khr_rate()
    currency = currency_mode  # Ensure currency is defined for use below

    def fetch_balance():
        from django.db.models import Count, Sum

        base_qs = Transaction.objects.filter(telegram_id=user_id)

        income_usd = base_qs.filter(transaction_type="income").aggregate(
            t=Sum("amount_usd")
        )["t"] or Decimal("0")
        expense_usd = base_qs.filter(transaction_type="expense").aggregate(
            t=Sum("amount_usd")
        )["t"] or Decimal("0")
        income_count = base_qs.filter(transaction_type="income").count()
        expense_count = base_qs.filter(transaction_type="expense").count()
        net = income_usd - expense_usd

        # This month
        today = _date.today()
        month_qs = base_qs.filter(
            transaction_date__year=today.year, transaction_date__month=today.month
        )
        month_income = month_qs.filter(transaction_type="income").aggregate(
            t=Sum("amount_usd")
        )["t"] or Decimal("0")
        month_expense = month_qs.filter(transaction_type="expense").aggregate(
            t=Sum("amount_usd")
        )["t"] or Decimal("0")

        # Today
        today_qs = base_qs.filter(transaction_date=today)
        today_income = today_qs.filter(transaction_type="income").aggregate(
            t=Sum("amount_usd")
        )["t"] or Decimal("0")
        today_expense = today_qs.filter(transaction_type="expense").aggregate(
            t=Sum("amount_usd")
        )["t"] or Decimal("0")

        # Top 3 expense categories
        top_cats = list(
            base_qs.filter(transaction_type="expense")
            .values("category_name")
            .annotate(total=Sum("amount_usd"), cnt=Count("id"))
            .order_by("-total")[:3]
        )

        return {
            "income_usd": income_usd,
            "expense_usd": expense_usd,
            "income_count": income_count,
            "expense_count": expense_count,
            "net": net,
            "month_income": month_income,
            "month_expense": month_expense,
            "today_income": today_income,
            "today_expense": today_expense,
            "top_cats": top_cats,
        }

    b = await asyncio.to_thread(fetch_balance)

    net_icon = _icon("net", value=b["net"])
    net_sign = "+" if b["net"] >= 0 else ""
    month_net = b["month_income"] - b["month_expense"]
    today_net = b["today_income"] - b["today_expense"]
    income_khr = b["income_usd"] * KHR
    expense_khr = b["expense_usd"] * KHR
    net_khr = b["net"] * KHR
    month_income_khr = b["month_income"] * KHR
    month_expense_khr = b["month_expense"] * KHR
    month_net_khr = month_net * KHR
    today_income_khr = b["today_income"] * KHR
    today_expense_khr = b["today_expense"] * KHR
    today_net_khr = today_net * KHR

    # Top categories
    cat_lines = []
    if b["top_cats"]:
        for i, c in enumerate(b["top_cats"], 1):
            total = c["total"] or Decimal("0")
            cat_name = html.escape(str(c["category_name"]))
            cat_lines.append(
                f"{i}. <b>{cat_name}</b> — <code>${total:,.2f}</code> | <code>៛{total * KHR:,.0f}</code>"
            )

    title = _t(
        lang,
        f"{_icon('balance')} សមតុល្យ {currency} (ដាច់ដោយឡែក)",
        f"{_icon('balance')} {currency} Balance (Separated)",
    )
    income_title = _t(lang, "ចំណូល", "Income")
    expense_title = _t(lang, "ចំណាយ", "Expenses")
    net_title = _t(lang, "នៅសល់", "Remaining")
    tx_label = _t(lang, "ប្រតិបត្តិការ", "transactions")
    this_month_title = _t(
        lang, f"{_icon('month_alt')} ខែនេះ", f"{_icon('month_alt')} This Month"
    )
    today_title = _t(lang, f"{_icon('calendar')} ថ្ងៃនេះ", f"{_icon('calendar')} Today")
    top_expense_title = _t(
        lang, f"{_icon('summary')} ចំណាយច្រើនបំផុត", f"{_icon('summary')} Top Expenses"
    )

    response_parts = [
        f"<b>{title}</b>",
        _receipt_divider(),
        f"• {income_title}: {_fmt(b['income'])}",
        f"• {expense_title}: {_fmt(b['expense'])}",
        f"• {net_icon} {net_title}: {net_sign}{_fmt(b['net'])}",
        "",
        _receipt_divider(),
        f"{_icon('note')} <i>{b['income_count']} {tx_label} ({income_title}) • {b['expense_count']} {tx_label} ({expense_title})</i>",
        "",
        f"<b>{this_month_title}</b>",
        f"• +{_fmt(b['month_income'])} / -{_fmt(b['month_expense'])} → {_fmt(month_net)}",
        "",
        _receipt_divider(),
        f"<b>{today_title}</b>",
        f"• +{_fmt(b['today_income'])} / -{_fmt(b['today_expense'])} → {_fmt(today_net)}",
    ]

    if b["top_cats"]:
        cat_lines = []
        for i, c in enumerate(b["top_cats"], 1):
            total = c["total"] or Decimal("0")
            cat_name = html.escape(str(c["category_name"]))
            cat_lines.append(f"{i}. <b>{cat_name}</b> — {_fmt(total)} ({c['cnt']}x)")
        response_parts.extend(
            ["", _receipt_divider(), f"<b>{top_expense_title}</b>", *cat_lines]
        )

    if b["net"] < 0:
        response_parts.extend(
            [
                "",
                _t(
                    lang,
                    f"<tg-spoiler>{_icon('warning')} ការព្រមាន: ចំណាយលើសចំណូល {_fmt(abs(b['net']))}</tg-spoiler>",
                    f"<tg-spoiler>{_icon('warning')} Warning: Expenses exceed income {_fmt(abs(b['net']))}</tg-spoiler>",
                ),
            ]
        )

    response = "\n".join(response_parts)
    # Add a toggle button for currency switch (USD <-> KHR)
    if currency == "USD":
        toggle_label = _t(lang, f"{_icon('fx')} KHR", f"{_icon('fx')} KHR")
        toggle_button = [_make_callback_button(toggle_label, "quick_fx")]
    else:
        toggle_label = _t(lang, f"{_icon('fx')} USD", f"{_icon('fx')} USD")
        toggle_button = [_make_callback_button(toggle_label, "quick_fx")]

    extra_rows = _report_extra_rows(lang, currency_mode=currency)
    # Insert the toggle button as the first row
    extra_rows = [toggle_button] + extra_rows

    await reply_with_menu(
        message,
        response,
        lang=lang,
        parse_mode=ParseMode.HTML,
        extra_rows=extra_rows,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process text, voice, photos, and documents for financial transactions."""
    if not update.message:
        return

    lang = _detect_user_lang(update, context)
    currency_mode = _normalize_currency_mode(context.user_data.get("currency_view"))
    context.user_data["currency_view"] = currency_mode

    # Check if this is a reply to a bot's transaction confirmation
    replied_text = (
        (update.message.reply_to_message.text or "")
        if update.message.reply_to_message
        else ""
    )
    is_tx_confirmation = "#" in replied_text and (
        "Recorded" in replied_text or "បានកត់ត្រា" in replied_text
    )

    if (
        update.message.reply_to_message
        and update.message.reply_to_message.from_user
        and update.message.reply_to_message.from_user.is_bot
        and update.message.text
        and is_tx_confirmation
    ):
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
            thinking_msg = await reply_with_menu(
                update.message,
                _t(
                    lang,
                    f"{_icon('mic')} កំពុងស្តាប់សារសំឡេង...",
                    f"{_icon('mic')} Processing voice message...",
                ),
                lang=lang,
                extra_rows=_entry_extra_rows(lang),
            )
            await update.message.chat.send_action(ChatAction.TYPING)

            # Download voice file
            voice_file = await context.bot.get_file(update.message.voice.file_id)
            voice_bytes = await voice_file.download_as_bytearray()

            # Use Gemini to transcribe and understand the voice message
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
                audio_part = {
                    "mime_type": "audio/ogg",
                    "data": bytes(audio_data),
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

            transcribed = await asyncio.to_thread(
                process_voice_with_gemini, voice_bytes
            )

            try:
                await thinking_msg.delete()
            except Exception:
                pass

            if not transcribed or transcribed == "UNCLEAR_AUDIO":
                await reply_with_menu(
                    update.message,
                    _t(
                        lang,
                        f"{_icon('mic')} មិនអាចស្តាប់សារសំឡេងបានច្បាស់ទេ។ សូមព្យាយាមម្ដងទៀត។",
                        f"{_icon('mic')} Could not understand the voice message. Please try again.",
                    ),
                    lang=lang,
                    extra_rows=_entry_extra_rows(lang),
                )
                return

            user_input = transcribed
            lang = _detect_user_lang(update, context, user_input)
            # Show what was transcribed
            await reply_with_menu(
                update.message,
                _t(
                    lang,
                    f"{_icon('mic')} *ស្តាប់បាន:* {user_input}",
                    f"{_icon('mic')} *Heard:* {user_input}",
                ),
                lang=lang,
                parse_mode=ParseMode.MARKDOWN,
                extra_rows=_entry_extra_rows(lang),
            )

        except Exception as e:
            await reply_with_menu(
                update.message,
                _t(
                    lang,
                    f"{_icon('error')} មានបញ្ហាពេលដំណើរការសំឡេង៖ {str(e)}",
                    f"{_icon('error')} Voice processing error: {str(e)}",
                ),
                lang=lang,
                extra_rows=_entry_extra_rows(lang),
            )
            return
    elif update.message.photo:
        # Photo: use Gemini Vision to read the image content
        try:
            thinking_msg = await reply_with_menu(
                update.message,
                _t(
                    lang,
                    f"{_icon('camera')} កំពុងអានរូបភាព...",
                    f"{_icon('camera')} Reading image...",
                ),
                lang=lang,
                extra_rows=_entry_extra_rows(lang),
            )
            await update.message.chat.send_action(ChatAction.TYPING)

            # Get the largest photo (last in array)
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

                image_part = {
                    "mime_type": "image/jpeg",
                    "data": bytes(img_data),
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

            result = await asyncio.to_thread(
                analyze_photo_with_gemini, photo_bytes, caption
            )

            try:
                await thinking_msg.delete()
            except Exception:
                pass

            if not result:
                await reply_with_menu(
                    update.message,
                    _t(
                        lang,
                        f"{_icon('camera')} មិនអាចអានរូបភាពបានទេ។ សូមព្យាយាមម្ដងទៀត។",
                        f"{_icon('camera')} Could not read the image. Please try again.",
                    ),
                    lang=lang,
                    extra_rows=_entry_extra_rows(lang),
                )
                return

            user_input = result
            lang = _detect_user_lang(update, context, user_input)
            await reply_with_menu(
                update.message,
                _t(
                    lang,
                    f"{_icon('camera')} *អានបាន:* {user_input}",
                    f"{_icon('camera')} *Read:* {user_input}",
                ),
                lang=lang,
                parse_mode=ParseMode.MARKDOWN,
                extra_rows=_entry_extra_rows(lang),
            )

        except Exception as e:
            await reply_with_menu(
                update.message,
                _t(
                    lang,
                    f"{_icon('error')} មានបញ្ហាពេលអានរូបភាព៖ {str(e)}",
                    f"{_icon('error')} Photo processing error: {str(e)}",
                ),
                lang=lang,
                extra_rows=_entry_extra_rows(lang),
            )
            return
    elif update.message.document:
        # Document: use caption if available
        if update.message.caption:
            user_input = update.message.caption
        else:
            await reply_with_menu(
                update.message,
                _t(
                    lang,
                    f"{_icon('document')} សូមភ្ជាប់ caption ជាមួយឯកសារ ដូចជា 'ចំណាយ $5 អាហារ'។",
                    f"{_icon('document')} Please include a caption with the document, e.g. 'spent $5 on lunch'.",
                ),
                lang=lang,
                extra_rows=_entry_extra_rows(lang),
            )
            return
    else:
        # Unsupported message type
        await reply_with_menu(
            update.message,
            _t(
                lang,
                f"{_icon('info')} ខ្ញុំអាចដំណើរការសារអក្សរ សារសំឡេង រូបភាព និងឯកសារដែលមាន caption បាន។\nសាកផ្ញើសារដូចជា 'ចំណាយ $5 អាហារ' ឬឆ្លើយតបទៅ media ជាមួយ caption។",
                f"{_icon('info')} I can process text, voice, photos, and documents with captions.\nSend a message like 'spent $5 on lunch' or reply to media with a caption.",
            ),
            lang=lang,
            extra_rows=_entry_extra_rows(lang),
        )
        return

    if not user_input:
        return

    try:
        # Detect language for thinking message
        lang = _detect_user_lang(update, context, user_input)
        thinking_msg = await reply_with_menu(
            update.message,
            _t(
                lang,
                f"{_icon('thinking')} កំពុងវិភាគសំណើរបស់អ្នក...",
                f"{_icon('thinking')} Analyzing your request...",
            ),
            lang=lang,
        )
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
        if not data.get("is_transaction", True):
            # Check if it's a summary/report request
            if data.get("is_summary"):
                await handle_summary(
                    update, user_id, data, lang, currency_mode=currency_mode
                )
                return
            # Check if it's a balance query
            if data.get("is_balance"):
                await handle_balance_currency(update, user_id, lang, currency_mode)
                return
            response = data.get(
                "message",
                _t(
                    lang,
                    "នេះមិនមែនជាប្រតិបត្តិការហិរញ្ញវត្ថុទេ។",
                    "This does not appear to be a financial transaction.",
                ),
            )
            await reply_with_menu(
                update.message,
                f"{_icon('info')} {response}",
                lang=lang,
                extra_rows=_help_extra_rows(lang, currency_mode=currency_mode),
            )
            return

        # Validate required fields
        if not data.get("amount"):
            raise ValueError("Parsed data missing required field: amount")
        if not data.get("category"):
            raise ValueError("Parsed data missing required field: category")
        if not data.get("type"):
            raise ValueError("Parsed data missing required field: type")

        # Parse amount into Decimal (allow strings like "$1,234.56")
        def parse_amount(value):
            if isinstance(value, (int, float, Decimal)):
                return Decimal(str(value))
            if isinstance(value, str):
                # remove currency symbols and commas
                cleaned = value.replace("$", "").replace(",", "").strip()
                return Decimal(cleaned)
            raise InvalidOperation("unsupported amount type")

        try:
            amount_dec = parse_amount(data["amount"])
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
            tx_date = parse_date(data.get("date"))
        except ValueError:
            # fallback to today if parsing fails
            tx_date = _date.today()

        tx_type = str(data.get("type")).lower()
        if tx_type not in ("income", "expense"):
            raise ValueError("Parsed field 'type' must be 'income' or 'expense'")

        # 2. Save to database automatically (run in thread to avoid async ORM call)
        from tracker.models import Category

        # Get or create category
        category_name = data.get("category", "Other")
        category, _ = await asyncio.to_thread(
            Category.objects.get_or_create,
            name=category_name,
            defaults={"icon": _icon("balance")},
        )

        # Parse currency info
        currency = data.get("currency", "USD").upper()
        if currency not in ("USD", "KHR"):
            currency = "USD"

        # Always recalculate using the latest real-time rate for consistency
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

        # Budget alert check after transaction (expenses only)
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
                    await send_with_menu(
                        context.bot,
                        user_id,
                        _t(
                            lang,
                            f"{_icon('warning')} ថវិកា {budget.category.name}: {budget.get_percentage_used():.0f}% (${budget.get_spent_amount():.2f}/{budget.limit_amount:.2f})",
                            f"{_icon('warning')} Budget {budget.category.name}: {budget.get_percentage_used():.0f}% (${budget.get_spent_amount():.2f}/{budget.limit_amount:.2f})",
                        ),
                        lang=lang,
                        parse_mode=ParseMode.MARKDOWN,
                        extra_rows=_report_extra_rows(
                            lang, currency_mode=currency_mode
                        ),
                    )

        # 3. Success Feedback
        currency_symbol = "$" if currency == "USD" else "៛"
        if lang == LANG_KH:
            response = (
                f"<b>{_icon('success')} បានកត់ត្រា {('ចំណាយ' if tx_type == 'expense' else 'ចំណូល')} #{tx.id}</b>\n"
                f"{_receipt_divider()}\n"
                f"{_icon('balance')} ចំនួន: {currency_symbol}{amount_dec:,.2f} ({currency})\n"
                f"{_icon('fx')} USD: ${amount_usd:,.2f} | KHR: ៛{amount_khr:,.0f}\n"
                f"{_icon('category')} ប្រភេទ: {category.icon} {category_name}\n"
                f"{_icon('note')} កំណត់សម្គាល់: {data.get('note', 'មិនមាន')}\n"
                f"{_receipt_divider()}\n"
                f"<i>{_icon('back')} ឆ្លើយតបសារនេះដើម្បីកែ ឬលុប</i>"
            )
        else:
            response = (
                f"<b>{_icon('success')} Recorded {tx_type} #{tx.id}</b>\n"
                f"{_receipt_divider()}\n"
                f"{_icon('balance')} Amount: {currency_symbol}{amount_dec:,.2f} ({currency})\n"
                f"{_icon('fx')} USD: ${amount_usd:,.2f} | KHR: ៛{amount_khr:,.0f}\n"
                f"{_icon('category')} Category: {category.icon} {category_name}\n"
                f"{_icon('note')} Note: {data.get('note', 'N/A')}\n"
                f"{_receipt_divider()}\n"
                f"<i>{_icon('back')} Reply to this message to edit or delete</i>"
            )
        await reply_with_menu(
            update.message,
            response,
            lang=lang,
            parse_mode=ParseMode.HTML,
            extra_rows=_entry_extra_rows(lang),
        )

        # 4. Available Balance Alert — warn if expenses exceed income
        if tx_type == "expense":

            def check_balance():
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
                alert = _t(
                    lang,
                    f"{_icon('warning')} *ការជូនដំណឹងសមតុល្យ*\n\n{_icon('net_negative')} ចំណាយលើសចំណូល!\n\n{_icon('income')} ចំណូលសរុប: ${total_income:,.2f} | ៛{total_income * rate:,.0f}\n{_icon('expense')} ចំណាយសរុប: ${total_expense:,.2f} | ៛{total_expense * rate:,.0f}\n{_icon('deficit')} ខ្វះ: -${deficit_usd:,.2f} | -៛{deficit_khr:,.0f}\n\n{_icon('tip')} *ណែនាំ:* សូមកាត់បន្ថយចំណាយ ឬបន្ថែមចំណូល។",
                    f"{_icon('warning')} *Available Balance Alert*\n\n{_icon('net_negative')} Expenses exceed income!\n\n{_icon('income')} Total Income: ${total_income:,.2f} | ៛{total_income * rate:,.0f}\n{_icon('expense')} Total Expenses: ${total_expense:,.2f} | ៛{total_expense * rate:,.0f}\n{_icon('deficit')} Deficit: -${deficit_usd:,.2f} | -៛{deficit_khr:,.0f}\n\n{_icon('tip')} *Tip:* Consider reducing expenses or adding income.",
                )
                await send_with_menu(
                    context.bot,
                    user_id,
                    alert,
                    lang=lang,
                    parse_mode=ParseMode.MARKDOWN,
                    extra_rows=_entry_extra_rows(lang),
                )

    except Exception as e:
        err_msg = str(e)
        if "quota" in err_msg.lower() or "rate" in err_msg.lower() or "429" in err_msg:
            await reply_with_menu(
                update.message,
                _t(
                    lang,
                    "⏳ សេវា AI រវល់បណ្ដោះអាសន្ន។ សូមព្យាយាមម្ដងទៀតក្នុង 1 នាទី។",
                    "⏳ AI service is temporarily busy. Please try again in 1 minute.",
                ),
                lang=lang,
                extra_rows=_entry_extra_rows(lang),
            )
        else:
            # Truncate to avoid Telegram 'Message too long' error
            if len(err_msg) > 300:
                err_msg = err_msg[:300] + "..."
            await reply_with_menu(
                update.message,
                _t(
                    lang,
                    f"{_icon('error')} មានបញ្ហា៖ {err_msg}",
                    f"{_icon('error')} Error: {err_msg}",
                ),
                lang=lang,
                extra_rows=_entry_extra_rows(lang),
            )


async def cmd_total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show total expenses and income."""
    user_id = update.message.from_user.id
    lang = _detect_user_lang(update, context)
    currency_mode = _normalize_currency_mode(context.user_data.get("currency_view"))

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
    if lang == LANG_KH:
        response = (
            f"{_icon('balance')} *សង្ខេបហិរញ្ញវត្ថុ*\n\n"
            f"{_icon('expense')} ចំណាយសរុប៖\n"
            f"   ${expenses_usd:,.2f} | ៛{expenses_usd * rate:,.0f}\n\n"
            f"{_icon('income')} ចំណូលសរុប៖\n"
            f"   ${income_usd:,.2f} | ៛{income_usd * rate:,.0f}\n\n"
            f"{_icon('summary')} សរុបនៅសល់៖\n"
            f"   ${net_usd:,.2f} | ៛{net_usd * rate:,.0f}"
        )
    else:
        response = (
            f"{_icon('balance')} *Financial Summary*\n\n"
            f"{_icon('expense')} Total Expenses:\n"
            f"   ${expenses_usd:,.2f} | ៛{expenses_usd * rate:,.0f}\n\n"
            f"{_icon('income')} Total Income:\n"
            f"   ${income_usd:,.2f} | ៛{income_usd * rate:,.0f}\n\n"
            f"{_icon('summary')} Net Balance:\n"
            f"   ${net_usd:,.2f} | ៛{net_usd * rate:,.0f}"
        )
    await reply_with_menu(
        update.message,
        response,
        lang=lang,
        parse_mode=ParseMode.MARKDOWN,
        extra_rows=_report_extra_rows(lang, currency_mode=currency_mode),
    )


async def cmd_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show total expenses."""
    user_id = update.message.from_user.id
    lang = _detect_user_lang(update, context)
    currency_mode = _normalize_currency_mode(context.user_data.get("currency_view"))

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
    response = _t(
        lang,
        f"{_icon('expense')} ចំណាយសរុប: ${total_usd:,.2f} | ៛{total_usd * rate:,.0f} ({count} ប្រតិបត្តិការ)",
        f"{_icon('expense')} Total Expenses: ${total_usd:,.2f} | ៛{total_usd * rate:,.0f} ({count} transactions)",
    )
    await reply_with_menu(
        update.message,
        response,
        lang=lang,
        parse_mode=ParseMode.MARKDOWN,
        extra_rows=_report_extra_rows(lang, currency_mode=currency_mode),
    )


async def cmd_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show total income."""
    user_id = update.message.from_user.id
    lang = _detect_user_lang(update, context)
    currency_mode = _normalize_currency_mode(context.user_data.get("currency_view"))

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
    response = _t(
        lang,
        f"{_icon('income')} ចំណូលសរុប: ${total_usd:,.2f} | ៛{total_usd * rate:,.0f} ({count} ប្រតិបត្តិការ)",
        f"{_icon('income')} Total Income: ${total_usd:,.2f} | ៛{total_usd * rate:,.0f} ({count} transactions)",
    )
    await reply_with_menu(
        update.message,
        response,
        lang=lang,
        parse_mode=ParseMode.MARKDOWN,
        extra_rows=_report_extra_rows(lang, currency_mode=currency_mode),
    )


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent transactions."""
    user_id = update.message.from_user.id
    lang = _detect_user_lang(update, context)
    currency_mode = _normalize_currency_mode(context.user.data.get("currency_view"))
    await send_recent_transactions(
        update.message, user_id, lang, currency_mode=currency_mode
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show start message with dashboard link."""
    user_id = update.message.from_user.id
    user = update.message.from_user
    user_name = user.first_name or ""
    if user.last_name:
        user_name = f"{user_name} {user.last_name}".strip()
    if not user_name.strip():
        user_name = "User"
    lang = _detect_user_lang(update, context)
    currency_mode = _normalize_currency_mode(context.user.data.get("currency_view"))
    context.user.data["currency_view"] = currency_mode
    app_url = _public_app_url()
    await reply_with_menu(
        update.message,
        _start_help_text(lang, user_name, user_id, app_url),
        lang=lang,
        parse_mode=ParseMode.HTML,
        extra_rows=None,  # No extra rows in main menu
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help and quick action buttons."""
    user_id = update.message.from_user.id
    user = update.message.from_user
    user_name = user.first_name or ""
    if user.last_name:
        user_name = f"{user_name} {user.last_name}".strip()
    if not user_name.strip():
        user_name = "User"
    lang = _detect_user_lang(update, context)
    currency_mode = _normalize_currency_mode(context.user.data.get("currency_view"))
    await send_help_message(
        update.message, user_name, user_id, lang, currency_mode=currency_mode
    )


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a transaction by ID. Usage: /delete <transaction_id>"""
    user_id = update.message.from_user.id
    lang = _detect_user_lang(update, context)

    if not context.args:
        await reply_with_menu(
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
        await reply_with_menu(
            update.message,
            _t(
                lang,
                f"{_icon('error')} Transaction ID ត្រូវតែជាលេខ",
                f"{_icon('error')} Transaction ID must be a number",
            ),
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
        await reply_with_menu(
            update.message, response, lang=lang, parse_mode=ParseMode.MARKDOWN
        )
    else:
        await reply_with_menu(
            update.message,
            _t(
                lang,
                f"{_icon('error')} រកមិនឃើញប្រតិបត្តិការ #{transaction_id} ឬអ្នកគ្មានសិទ្ធិ",
                f"{_icon('error')} Transaction #{transaction_id} not found or unauthorized",
            ),
            lang=lang,
        )


async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit a transaction. Usage: /edit <transaction_id> <field> <value>
    Fields: amount, category, date (YYYY-MM-DD), note"""
    user_id = update.message.from_user.id
    lang = _detect_user_lang(update, context)

    if len(context.args) < 3:
        await reply_with_menu(
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
        await reply_with_menu(
            update.message,
            _t(
                lang,
                f"{_icon('error')} ទម្រង់បញ្ជាមិនត្រឹមត្រូវ",
                f"{_icon('error')} Invalid format",
            ),
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
        await reply_with_menu(
            update.message, response, lang=lang, parse_mode=ParseMode.MARKDOWN
        )
    else:
        await reply_with_menu(
            update.message, f"{_icon('error')} {error_msg}", lang=lang
        )


class Command(BaseCommand):
    help = "Runs the Telegram bot"

    def handle(self, *args, **options):
        import asyncio
        import atexit
        import fcntl

        import httpx
        from telegram.error import Conflict as TelegramConflict

        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            self.stdout.write(self.style.ERROR("TELEGRAM_BOT_TOKEN not found in .env"))
            return

        # --- Prevent multiple local run_bot instances ---
        lock_path = "/tmp/ai_finance_bot_run_bot.lock"
        lock_file = open(lock_path, "w")
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_file.write(str(os.getpid()))
            lock_file.flush()
        except BlockingIOError:
            self.stdout.write(
                self.style.ERROR(
                    "Another local run_bot instance is already running. "
                    "Stop it first (e.g., pkill -f 'manage.py run_bot') and retry."
                )
            )
            return

        def _release_lock():
            try:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
                lock_file.close()
            except Exception:
                pass

        atexit.register(_release_lock)

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
        app.add_handler(CommandHandler("help", cmd_help))
        app.add_handler(CommandHandler("total", cmd_total))
        app.add_handler(CommandHandler("expenses", cmd_expenses))
        app.add_handler(CommandHandler("income", cmd_income))
        app.add_handler(CommandHandler("list", cmd_list))
        app.add_handler(CallbackQueryHandler(handle_quick_action))
        register_rate_command(app)

        # Add message handler for text, voice, photo, and document messages
        app.add_handler(
            MessageHandler(
                (filters.TEXT | filters.VOICE | filters.PHOTO | filters.Document.ALL)
                & (~filters.COMMAND),
                handle_message,
            )
        )

        async def _on_error(update, context):
            if isinstance(context.error, TelegramConflict):
                self.stdout.write(
                    self.style.ERROR(
                        "Telegram polling conflict: another bot instance is already running "
                        "(local or remote). Stop other instances and start only one."
                    )
                )
                await context.application.stop()

        app.add_error_handler(_on_error)

        app.run_polling(
            drop_pending_updates=True, allowed_updates=["message", "callback_query"]
        )
