from decimal import Decimal
import re

try:
    import emoji as _emoji_lib
except Exception:
    _emoji_lib = None


class BotUI:
    LANG_EN = "en"
    LANG_KH = "km"

    ICONS = {
        "add": ":heavy_plus_sign:",
        "back": ":leftwards_arrow_with_hook:",
        "balance": ":money_bag:",
        "calendar": ":spiral_calendar_pad:",
        "camera": ":camera_with_flash:",
        "category": ":label:",
        "deficit": ":chart_decreasing:",
        "document": ":page_facing_up:",
        "error": ":x:",
        "expense": ":money_with_wings:",
        "fx": ":currency_exchange:",
        "help": ":sos:",
        "income": ":dollar:",
        "info": ":information_source:",
        "khr": ":cambodia:",
        "lang_en": ":us:",
        "lang_kh": ":cambodia:",
        "mic": ":microphone:",
        "month": ":spiral_calendar_pad:",
        "month_alt": ":spiral_calendar_pad:",
        "net_negative": ":chart_decreasing:",
        "new": ":new:",
        "note": ":memo:",
        "old": ":clock9:",
        "open_app": ":mobile_phone:",
        "question": ":question:",
        "recent": ":clock9:",
        "style": ":sparkles:",
        "success": ":white_check_mark:",
        "summary": ":bar_chart:",
        "thinking": ":robot_face:",
        "tip": ":bulb:",
        "today": ":calendar:",
        "update": ":pencil2:",
        "warning": ":warning:",
    }

    @staticmethod
    def fmt(val):
        try:
            return f"${val:,.2f}" if isinstance(val, (float, Decimal)) else str(val)
        except Exception:
            return str(val)

    @classmethod
    def t(cls, lang: str, kh_text: str, en_text: str) -> str:
        return kh_text if lang == cls.LANG_KH else en_text

    @staticmethod
    def emojize(raw: str) -> str:
        if _emoji_lib is None:
            return raw
        try:
            return _emoji_lib.emojize(raw, language="alias")
        except Exception:
            return raw

    @classmethod
    def icon(cls, name: str, **kwargs) -> str:
        if name == "net":
            value = kwargs.get("value", 0)
            return cls.emojize(":chart_increasing:" if value >= 0 else ":chart_decreasing:")
        if name == "tx_type":
            tx_type = str(kwargs.get("tx_type", "")).lower()
            if tx_type == "income":
                return cls.emojize(cls.ICONS["income"])
            if tx_type == "expense":
                return cls.emojize(cls.ICONS["expense"])
        return cls.emojize(cls.ICONS.get(name, "•"))

    @staticmethod
    def receipt_divider() -> str:
        return "───────────────────"

    @staticmethod
    def receipt_header_divider() -> str:
        return ""

    @classmethod
    def sanitize_text_icons(cls, text, keep_warning: bool = True) -> str:
        raw = "" if text is None else str(text)
        rendered = cls.emojize(raw)

        warning_placeholder = "__KEEP_WARNING_ICON__"
        warning_alias = cls.ICONS.get("warning", ":warning:")
        warning_glyph = cls.emojize(warning_alias)
        if keep_warning:
            rendered = rendered.replace(warning_alias, warning_placeholder)
            rendered = rendered.replace(warning_glyph, warning_placeholder)

        # Remove emoji glyphs from response text (keep icons only on buttons).
        if _emoji_lib is not None:
            try:
                rendered = _emoji_lib.replace_emoji(rendered, replace="")
            except Exception:
                pass

        # Remove remaining emoji aliases like :warning: when present.
        rendered = re.sub(r":[a-zA-Z0-9_+\-]+:", "", rendered)

        if keep_warning:
            rendered = rendered.replace(warning_placeholder, warning_glyph)

        # Normalize spaces after icon removal while preserving line breaks.
        rendered = re.sub(r"[ \t]{2,}", " ", rendered)
        rendered = re.sub(r"\n[ \t]+", "\n", rendered)
        return rendered.strip()

    @staticmethod
    def contains_khmer(text: str) -> bool:
        return any("\u1780" <= ch <= "\u17ff" for ch in text)

    @classmethod
    def detect_user_lang(cls, update, context, text: str | None = None) -> str:
        stored_lang = getattr(context, "user_data", {}).get("lang") if context else None
        if stored_lang in (cls.LANG_EN, cls.LANG_KH):
            return stored_lang

        if text and cls.contains_khmer(text):
            return cls.LANG_KH

        user = getattr(update, "effective_user", None)
        if user is None and getattr(update, "callback_query", None):
            user = update.callback_query.from_user
        if user is None and getattr(update, "message", None):
            user = update.message.from_user

        language_code = (getattr(user, "language_code", "") or "").lower()
        return cls.LANG_KH if language_code.startswith("km") else cls.LANG_EN
