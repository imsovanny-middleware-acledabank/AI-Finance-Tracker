# buttons.py
# All InlineKeyboardButton and menu row definitions for Telegram bot
from telegram import InlineKeyboardButton

try:
    import emoji as _emoji_lib
except Exception:
    _emoji_lib = None


def _emojize_text(text):
    raw = "" if text is None else str(text)
    if _emoji_lib is None:
        return raw
    try:
        return _emoji_lib.emojize(raw, language="alias")
    except Exception:
        return raw


_DEFAULT_ICONS = {
    "add": ":heavy_plus_sign:",
    "balance": ":money_bag:",
    "fx": ":currency_exchange:",
    "help": ":sos:",
    "lang_en": ":us:",
    "lang_kh": ":cambodia:",
    "month": ":spiral_calendar_pad:",
    "open_app": ":mobile_phone:",
    "recent": ":clock9:",
    "summary": ":bar_chart:",
    "today": ":calendar:",
}


def _resolve_t(translator):
    return translator or (lambda lang, kh_text, en_text: kh_text if lang == "km" else en_text)


def _resolve_icon(icon_func, icons):
    icon_map = icons or _DEFAULT_ICONS
    if icon_func:
        return icon_func
    return lambda name: _emojize_text(icon_map.get(name, "•"))


def _resolve_icons(icons):
    return icons or _DEFAULT_ICONS

def make_callback_button(text, callback_data):
    return InlineKeyboardButton(_emojize_text(text), callback_data=callback_data)

def build_help_support_rows(lang, nav_stack=None):
    rows = [
        [
            make_callback_button(
                ":blue_book: របៀបប្រើប្រាស់" if lang == "km" else ":blue_book: User Guide",
                "usage_instructions",
            )
        ]
    ]
    if nav_stack and len(nav_stack) > 1:
        rows.append(
            [
                make_callback_button(
                    ":left_arrow: ត្រឡប់ក្រោយ" if lang == "km" else ":left_arrow: Back",
                    "quick_back_main",
                ),
                make_callback_button(
                    ":house: ទំព័រដើម" if lang == "km" else ":house: Home",
                    "quick_home_all",
                ),
            ]
        )
    return rows

def _base_menu_rows(lang, include_show_all=True, include_lang=True, _public_login_url=None, _t=None, _icon=None, ICONS=None, InlineKeyboardButton=None, WebAppInfo=None):
    _t = _resolve_t(_t)
    _icon = _resolve_icon(_icon, ICONS)
    ICONS = _resolve_icons(ICONS)
    rows = []
    login_url = _public_login_url() if _public_login_url else None
    if login_url:
        rows.append([
            InlineKeyboardButton(
                _t(
                    lang,
                    f"{_icon('open_app')} បើកកម្មវិធី",
                    f"{_icon('open_app')} Open App",
                ),
                web_app=WebAppInfo(url=login_url),
            )
        ])
    if include_show_all:
        rows.append([
            make_callback_button(
                _t(lang, "បង្ហាញប៊ូតុងទាំងអស់", "Show All Buttons"), "show_all_buttons"
            )
        ])
    if include_lang:
        if lang == "km":
            rows.append([
                make_callback_button(f"{ICONS['lang_en']} English", "quick_lang_en")
            ])
        else:
            rows.append([
                make_callback_button(f"{ICONS['lang_kh']} Khmer", "quick_lang_kh")
            ])
    return rows

def _entry_extra_rows(lang, _t=None, _icon=None):
    _t = _resolve_t(_t)
    _icon = _resolve_icon(_icon, None)
    return [
        [
            make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណាយ", f"{_icon('add')} Add Expense"),
                "quick_add_expense",
            ),
            make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណូល", f"{_icon('add')} Add Income"),
                "quick_add_income",
            ),
        ],
        [
            make_callback_button(_t(lang, "⬅️ ត្រឡប់ក្រោយ", "⬅️ Back"), "quick_back_main"),
            make_callback_button(_t(lang, "🏠 ទំព័រដើម", "🏠 Home"), "quick_home_all"),
        ],
    ]

def _report_extra_rows(lang, currency_mode="USD", _t=None, _icon=None):
    _t = _resolve_t(_t)
    _icon = _resolve_icon(_icon, None)
    return [
        [
            make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណាយ", f"{_icon('add')} Add Expense"),
                "quick_add_expense",
            ),
            make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណូល", f"{_icon('add')} Add Income"),
                "quick_add_income",
            ),
        ],
        [
            make_callback_button(
                _t(lang, f"{_icon('recent')} បញ្ជីថ្មីៗ", f"{_icon('recent')} Recent"),
                "quick_list",
            ),
            make_callback_button(
                _t(lang, f"{_icon('summary')} សរុប", f"{_icon('summary')} Summary"),
                "quick_summary",
            ),
        ],
        [
            make_callback_button(_t(lang, "⬅️ ត្រឡប់ក្រោយ", "⬅️ Back"), "quick_back_main"),
            make_callback_button(_t(lang, "🏠 ទំព័រដើម", "🏠 Home"), "quick_home_all"),
        ],
    ]

def _help_extra_rows(lang, currency_mode="USD", _t=None, _icon=None):
    _t = _resolve_t(_t)
    _icon = _resolve_icon(_icon, None)
    return [
        [
            make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណាយ", f"{_icon('add')} Add Expense"),
                "quick_add_expense",
            ),
            make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណូល", f"{_icon('add')} Add Income"),
                "quick_add_income",
            ),
        ],
        [
            make_callback_button(
                _t(lang, f"{_icon('recent')} បញ្ជីថ្មីៗ", f"{_icon('recent')} Recent"),
                "quick_list",
            ),
            make_callback_button(
                _t(lang, f"{_icon('summary')} សរុប", f"{_icon('summary')} Summary"),
                "quick_summary",
            ),
        ],
    ]

def _all_buttons_extra_rows(lang, _t=None, _icon=None, ICONS=None):
    _t = _resolve_t(_t)
    _icon = _resolve_icon(_icon, ICONS)
    ICONS = _resolve_icons(ICONS)
    rows = [
        [
            make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណាយ", f"{_icon('add')} Add Expense"),
                "quick_add_expense",
            ),
            make_callback_button(
                _t(lang, f"{_icon('add')} បន្ថែមចំណូល", f"{_icon('add')} Add Income"),
                "quick_add_income",
            ),
        ],
        [
            make_callback_button(
                _t(lang, f"{_icon('balance')} សមតុល្យ", f"{_icon('balance')} Balance"),
                "quick_balance",
            ),
            make_callback_button(
                _t(lang, f"{_icon('today')} ថ្ងៃនេះ", f"{_icon('today')} Today"),
                "quick_today",
            ),
        ],
        [
            make_callback_button(
                _t(lang, f"{_icon('month')} ខែនេះ", f"{_icon('month')} This Month"),
                "quick_month",
            ),
            make_callback_button(
                _t(lang, f"{_icon('fx')} KHR", f"{_icon('fx')} USD"), "quick_fx"
            ),
        ],
        [
            make_callback_button(
                _t(lang, f"{_icon('recent')} បញ្ជីថ្មីៗ", f"{_icon('recent')} Recent"),
                "quick_list",
            ),
            make_callback_button(
                _t(lang, f"{_icon('summary')} សរុប", f"{_icon('summary')} Summary"),
                "quick_summary",
            ),
        ],
        [
            make_callback_button(
                _t(lang, f"{_icon('help')} ជំនួយ", f"{_icon('help')} Help"), "quick_help"
            ),
        ],
        [
            make_callback_button(
                _t(lang, "បិទប៊ូតុងទាំងអស់", "Hide All Buttons"), "hide_all_buttons"
            ),
        ],
    ]
    if lang == "km":
        rows.append([
            make_callback_button(f"{ICONS['lang_en']} English", "quick_lang_en")
        ])
    else:
        rows.append([
            make_callback_button(f"{ICONS['lang_kh']} Khmer", "quick_lang_kh")
        ])
    return rows
