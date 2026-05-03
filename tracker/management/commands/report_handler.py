"""Report handler — balance and summary financial reports."""
import asyncio
import html
from decimal import Decimal

from telegram import Update
from telegram.constants import ParseMode

from .bot_ui import BotUI
from .exchange_rate import fetch_usd_to_khr_rate
from .menu_service import MenuService

LANG_EN = BotUI.LANG_EN
LANG_KH = BotUI.LANG_KH


def _t(lang: str, kh_text: str, en_text: str) -> str:
    return BotUI.t(lang, kh_text, en_text)


def _icon(name: str, **kwargs) -> str:
    return BotUI.icon(name, **kwargs)


def _receipt_divider() -> str:
    return BotUI.receipt_divider()


class ReportHandler:
    """Generates financial summary and balance reports."""

    @staticmethod
    async def handle_balance_currency(update, user_id, lang: str, currency_mode: str):
        """Wrapper — delegates to handle_balance with the given currency."""
        await ReportHandler.handle_balance(update, user_id, lang, currency_mode=currency_mode)

    @staticmethod
    async def handle_summary(
        update: Update, user_id, data: dict, lang: str, currency_mode: str = "USD"
    ):
        """Generate a financial summary report for day / month / year."""
        from datetime import date as _date

        from django.db.models import Count, Q, Sum

        from tracker.models import Transaction

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

            top_cats = (
                qs.filter(transaction_type="expense")
                .values("category_name")
                .annotate(total=Sum("amount_usd"), cnt=Count("id"))
                .order_by("-total")[:5]
            )

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
        currency = (currency_mode or "USD").upper()
        if currency not in {"USD", "KHR"}:
            currency = "USD"

        cat_lines = []
        if s["top_cats"]:
            for i, c in enumerate(s["top_cats"], 1):
                total = c["total"] or Decimal("0")
                cat_name = html.escape(str(c["category_name"]))
                display_total = f"${total:,.2f}" if currency == "USD" else f"៛{total * KHR:,.0f}"
                cat_lines.append(
                    f"{i}. <b>{cat_name}</b> — {display_total} ({c['cnt']}x)"
                )

        daily_lines = []
        if s["daily_data"]:
            for d in s["daily_data"]:
                day = d["transaction_date"]
                d_inc = d["day_income"] or Decimal("0")
                d_exp = d["day_expense"] or Decimal("0")
                d_net = d_inc - d_exp
                d_icon = _icon("net", value=d_net)
                if currency == "USD":
                    day_income = f"${d_inc:,.2f}"
                    day_expense = f"${d_exp:,.2f}"
                    day_net = f"${d_net:,.2f}"
                else:
                    day_income = f"៛{d_inc * KHR:,.0f}"
                    day_expense = f"៛{d_exp * KHR:,.0f}"
                    day_net = f"៛{d_net * KHR:,.0f}"
                daily_lines.append(
                    f"• <b>{day.strftime('%d %b')}</b>: +{day_income} -{day_expense} {d_icon} {day_net}"
                )

        title = _t(
            lang,
            f"{_icon('summary')} របាយការណ៍{s['period_kh']}",
            f"{_icon('summary')} Financial Summary",
        )
        label_title = _t(lang, "រយៈពេល", "Period")
        section_title = _t(
            lang,
            f"{_icon('income') if currency == 'USD' else _icon('khr')} ផ្នែក{'ដុល្លារ' if currency == 'USD' else 'រៀល'} ({currency})",
            f"{_icon('income') if currency == 'USD' else _icon('khr')} {currency} Section",
        )
        income_title = _t(lang, "ចំណូល", "Income")
        expense_title = _t(lang, "ចំណាយ", "Expenses")
        net_title = _t(lang, "នៅសល់", "Net Balance")
        tx_count_label = _t(lang, "ប្រតិបត្តិការ", "transactions")
        cat_title = _t(lang, f"{_icon('summary')} ចំណាយតាមប្រភេទ", f"{_icon('summary')} Expenses by Category")
        days_title = _t(lang, f"{_icon('calendar')} ថ្ងៃថ្មីៗ", f"{_icon('calendar')} Recent Days")

        if currency == "USD":
            display_income = f"${s['income_usd']:,.2f}"
            display_expense = f"${s['expense_usd']:,.2f}"
            display_net = f"{net_sign}${s['net']:,.2f}"
        else:
            display_income = f"៛{income_khr:,.0f}"
            display_expense = f"៛{expense_khr:,.0f}"
            display_net = f"{net_sign}៛{net_khr:,.0f}"

        response_parts = [
            f"<b>{title}</b>",
            _receipt_divider(),
            f"<blockquote>{label_title}: {html.escape(s['label'])}</blockquote>",
            "",
            f"<b>{section_title}</b>",
            f"• {income_title}: {display_income}",
            f"• {expense_title}: {display_expense}",
            f"• {net_icon} {net_title}: {display_net}",
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
                        f"{_icon('warning')} <b>ការព្រមាន៖</b> ចំណាយលើសចំណូល សូមពិចារណាកាត់បន្ថយចំណាយ។",
                        f"{_icon('warning')} <b>Warning:</b> Expenses exceed income. Consider reducing spending.",
                    ),
                ]
            )

        from .buttons import make_callback_button

        toggle_label = _t(lang, f"{_icon('fx')} KHR", f"{_icon('fx')} KHR") if currency == "USD" else _t(lang, f"{_icon('fx')} USD", f"{_icon('fx')} USD")
        toggle_button = [make_callback_button(toggle_label, "quick_fx")]
        extra_rows = [toggle_button] + MenuService.report_extra_rows(lang, currency_mode=currency)

        await MenuService.reply_with_menu(
            message,
            "\n".join(response_parts),
            lang=lang,
            parse_mode=ParseMode.HTML,
            extra_rows=extra_rows,
        )

    @staticmethod
    async def handle_balance(
        update: Update, user_id, lang: str, currency_mode: str = "USD"
    ):
        """Show the user's current balance: total income, total expenses, and remaining."""
        from decimal import Decimal

        from django.db.models import Count, Sum

        from tracker.models import Transaction

        message = update.message if getattr(update, "message", None) else update
        currency = currency_mode

        KHR = await fetch_usd_to_khr_rate()

        def _date_today():
            from datetime import date as _date
            return _date.today()

        def fetch_balance():
            from datetime import date as _date

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

            today_qs = base_qs.filter(transaction_date=today)
            today_income = today_qs.filter(transaction_type="income").aggregate(
                t=Sum("amount_usd")
            )["t"] or Decimal("0")
            today_expense = today_qs.filter(transaction_type="expense").aggregate(
                t=Sum("amount_usd")
            )["t"] or Decimal("0")

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

        def _fmt_currency(value):
            return f"${value:,.2f}" if currency == "USD" else f"៛{value:,.0f}"

        if currency == "USD":
            display_income = b["income_usd"]
            display_expense = b["expense_usd"]
            display_net = b["net"]
            display_month_income = b["month_income"]
            display_month_expense = b["month_expense"]
            display_month_net = month_net
            display_today_income = b["today_income"]
            display_today_expense = b["today_expense"]
            display_today_net = today_net
        else:
            display_income = income_khr
            display_expense = expense_khr
            display_net = net_khr
            display_month_income = month_income_khr
            display_month_expense = month_expense_khr
            display_month_net = month_net_khr
            display_today_income = today_income_khr
            display_today_expense = today_expense_khr
            display_today_net = today_net_khr

        title = _t(
            lang,
            f"{_icon('balance')} សមតុល្យ {currency} (ដាច់ដោយឡែក)",
            f"{_icon('balance')} {currency} Balance (Separated)",
        )
        income_title = _t(lang, "ចំណូល", "Income")
        expense_title = _t(lang, "ចំណាយ", "Expenses")
        net_title = _t(lang, "នៅសល់", "Remaining")
        tx_label = _t(lang, "ប្រតិបត្តិការ", "transactions")
        this_month_title = _t(lang, f"{_icon('month_alt')} ខែនេះ", f"{_icon('month_alt')} This Month")
        today_title = _t(lang, f"{_icon('calendar')} ថ្ងៃនេះ", f"{_icon('calendar')} Today")
        top_expense_title = _t(lang, f"{_icon('summary')} ចំណាយច្រើនបំផុត", f"{_icon('summary')} Top Expenses")

        response_parts = [
            f"<b>{title}</b>",
            _receipt_divider(),
            f"• {income_title}: {_fmt_currency(display_income)}",
            f"• {expense_title}: {_fmt_currency(display_expense)}",
            f"• {net_icon} {net_title}: {net_sign}{_fmt_currency(abs(display_net)) if display_net < 0 else _fmt_currency(display_net)}",
            "",
            _receipt_divider(),
            f"{_icon('note')} <i>{b['income_count']} {tx_label} ({income_title}) • {b['expense_count']} {tx_label} ({expense_title})</i>",
            "",
            f"<b>{this_month_title}</b>",
            f"• +{_fmt_currency(display_month_income)} / -{_fmt_currency(display_month_expense)} → {_fmt_currency(display_month_net)}",
            "",
            _receipt_divider(),
            f"<b>{today_title}</b>",
            f"• +{_fmt_currency(display_today_income)} / -{_fmt_currency(display_today_expense)} → {_fmt_currency(display_today_net)}",
        ]

        if b["top_cats"]:
            cat_lines = []
            for i, c in enumerate(b["top_cats"], 1):
                total = c["total"] or Decimal("0")
                cat_name = html.escape(str(c["category_name"]))
                display_total = total if currency == "USD" else total * KHR
                cat_lines.append(
                    f"{i}. <b>{cat_name}</b> — {_fmt_currency(display_total)} ({c['cnt']}x)"
                )
            response_parts.extend(
                ["", _receipt_divider(), f"<b>{top_expense_title}</b>", *cat_lines]
            )

        if b["net"] < 0:
            response_parts.extend(
                [
                    "",
                    _t(
                        lang,
                        f"{_icon('warning')} <b>ការព្រមាន:</b> ចំណាយលើសចំណូល {_fmt_currency(abs(display_net))}",
                        f"{_icon('warning')} <b>Warning:</b> Expenses exceed income {_fmt_currency(abs(display_net))}",
                    ),
                ]
            )

        # Currency toggle button
        if currency == "USD":
            toggle_label = _t(lang, f"{_icon('fx')} KHR", f"{_icon('fx')} KHR")
        else:
            toggle_label = _t(lang, f"{_icon('fx')} USD", f"{_icon('fx')} USD")

        from .buttons import make_callback_button

        toggle_button = [make_callback_button(toggle_label, "quick_fx")]
        extra_rows = [toggle_button] + MenuService.report_extra_rows(lang, currency_mode=currency)

        await MenuService.reply_with_menu(
            message,
            "\n".join(response_parts),
            lang=lang,
            parse_mode=ParseMode.HTML,
            extra_rows=extra_rows,
        )
