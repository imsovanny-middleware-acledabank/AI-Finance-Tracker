"""API views for the finance tracker app."""

import csv
from datetime import date, datetime, timedelta
from urllib.parse import quote

from asgiref.sync import async_to_sync
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse
from django.shortcuts import redirect, render
from rest_framework.views import APIView
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from tracker.models import Category, ChatMessage, Transaction
from tracker.serializers import (
    StatisticsSerializer,
    TransactionListSerializer,
    TransactionSerializer,
)
from tracker.services import analyze_finance_text
from tracker.management.commands.exchange_rate import (
    USD_KHR_FALLBACK_RATE,
    fetch_usd_to_khr_rate,
)


def _get_khr_rate_float() -> float:
    """Get USD->KHR rate as float, with safe fallback."""
    try:
        return float(async_to_sync(fetch_usd_to_khr_rate)())
    except Exception:
        return float(USD_KHR_FALLBACK_RATE)


def _parse_date_range(request):
    """Parse date_from and date_to query params, return (date_from, date_to) or (None, None)."""
    df = request.query_params.get("date_from")
    dt = request.query_params.get("date_to")
    try:
        date_from = datetime.strptime(df, "%Y-%m-%d").date() if df else None
        date_to = datetime.strptime(dt, "%Y-%m-%d").date() if dt else None
    except (ValueError, TypeError):
        date_from, date_to = None, None
    return date_from, date_to


def _filter_by_date(qs, date_from, date_to):
    """Apply date range filter to a queryset."""
    if date_from:
        qs = qs.filter(transaction_date__gte=date_from)
    if date_to:
        qs = qs.filter(transaction_date__lte=date_to)
    return qs


def dashboard_view(request):
    """Render the dashboard template."""
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        return redirect(f"/login/?next={quote(request.get_full_path() or '/')}")
    return render(request, "dashboard.html")


class ExchangeRateAPIView(APIView):
    """Return current USD->KHR exchange rate for dashboard clients."""

    permission_classes = [AllowAny]

    def get(self, request):
        rate = _get_khr_rate_float()
        return Response({"rate": rate, "base": "USD", "quote": "KHR"})


class SessionTelegramAPIMixin:
    """Shared session-based telegram auth helpers for API views."""

    permission_classes = [AllowAny]

    def _session_telegram_id(self):
        telegram_id = self.request.session.get("telegram_id")
        if not telegram_id:
            return None
        try:
            return int(telegram_id)
        except (TypeError, ValueError):
            return None

    def _require_session_telegram_id(self):
        telegram_id = self._session_telegram_id()
        if telegram_id is None:
            return None, Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return telegram_id, None


def _recent_transactions_response(request, telegram_id: int):
    """Build recent/view transactions response."""
    limit = int(request.query_params.get("limit", 20))
    transactions = (
        _filter_by_date(
            Transaction.objects.filter(telegram_id=telegram_id),
            *_parse_date_range(request),
        )
        .select_related("category")
        .order_by("transaction_date", "created_at")[:limit]
    )

    khr_rate = _get_khr_rate_float()
    result = []
    for tx in transactions:
        amt_usd = float(tx.amount_usd) if tx.amount_usd else float(tx.amount)
        amt_khr = float(tx.amount_khr) if tx.amount_khr else amt_usd * khr_rate
        result.append(
            {
                "id": tx.id,
                "amount": float(tx.amount),
                "amount_usd": amt_usd,
                "amount_khr": amt_khr,
                "currency": tx.currency or "USD",
                "type": tx.transaction_type,
                "category": (
                    f"{tx.category.icon} {tx.category.name}"
                    if tx.category
                    else tx.category_name
                ),
                "description": tx.note or "",
                "date": tx.transaction_date.isoformat(),
                "created_at": tx.created_at.isoformat(),
            }
        )
    return Response(result)


def _delete_transaction_response(telegram_id: int, transaction_id):
    """Delete a transaction and return API response."""
    if not transaction_id:
        return Response(
            {"error": "transaction_id required"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        transaction = Transaction.objects.get(id=transaction_id, telegram_id=telegram_id)
        transaction_info = {
            "id": transaction.id,
            "amount": float(transaction.amount),
            "category": transaction.category_name,
            "date": transaction.transaction_date.isoformat(),
        }
        transaction.delete()
        return Response(
            {
                "success": True,
                "message": "Transaction deleted successfully",
                "deleted": transaction_info,
            }
        )
    except Transaction.DoesNotExist:
        return Response(
            {"error": "Transaction not found or unauthorized"},
            status=status.HTTP_404_NOT_FOUND,
        )


def _create_transaction_response(telegram_id: int, payload):
    """Create a transaction from request payload and return API response."""
    try:
        amount = float(payload.get("amount", 0))
        if amount <= 0:
            return Response(
                {"error": "Amount must be positive"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except (ValueError, TypeError):
        return Response({"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)

    tx_type = payload.get("transaction_type", "expense")
    if tx_type not in ("income", "expense"):
        return Response({"error": "Invalid type"}, status=status.HTTP_400_BAD_REQUEST)

    currency = payload.get("currency", "USD")
    if currency not in ("USD", "KHR"):
        currency = "USD"

    khr_rate = _get_khr_rate_float()
    if currency == "KHR":
        amount_khr = amount
        amount_usd = round(amount / khr_rate, 2)
    else:
        amount_usd = amount
        amount_khr = round(amount * khr_rate, 2)

    category_name = payload.get("category_name", "Other")
    category = None
    try:
        category = Category.objects.get(name__iexact=category_name)
        category_name = category.name
    except Category.DoesNotExist:
        pass

    tx_date = payload.get("transaction_date")
    if tx_date:
        try:
            tx_date = datetime.strptime(tx_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            tx_date = date.today()
    else:
        tx_date = date.today()

    note = payload.get("note", "")

    transaction = Transaction.objects.create(
        telegram_id=telegram_id,
        amount=amount,
        currency=currency,
        amount_usd=amount_usd,
        amount_khr=amount_khr,
        category=category,
        category_name=category_name,
        transaction_type=tx_type,
        note=note,
        transaction_date=tx_date,
    )

    return Response(
        {
            "status": "success",
            "success": True,
            "message": "Transaction added",
            "transaction": {
                "id": transaction.id,
                "amount": float(transaction.amount),
                "amount_usd": float(transaction.amount_usd),
                "amount_khr": float(transaction.amount_khr),
                "currency": transaction.currency,
                "category": transaction.category_name,
                "type": transaction.transaction_type,
                "date": transaction.transaction_date.isoformat(),
                "note": transaction.note or "",
            },
        },
        status=status.HTTP_201_CREATED,
    )


def _update_transaction_response(telegram_id: int, transaction_id, payload):
    """Update a transaction and return API response."""
    if not transaction_id:
        return Response(
            {"error": "transaction_id required"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        transaction = Transaction.objects.get(id=transaction_id, telegram_id=telegram_id)

        if "amount" in payload:
            raw_amount = payload.get("amount")
            if raw_amount not in (None, ""):
                try:
                    new_amount = float(raw_amount)
                    if new_amount <= 0:
                        return Response(
                            {"error": "Amount must be positive"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    transaction.amount = new_amount
                    khr_rate = _get_khr_rate_float()
                    cur = transaction.currency or "USD"
                    if cur == "KHR":
                        transaction.amount_khr = new_amount
                        transaction.amount_usd = round(new_amount / khr_rate, 2)
                    else:
                        transaction.amount_usd = new_amount
                        transaction.amount_khr = round(new_amount * khr_rate, 2)
                except (ValueError, TypeError):
                    return Response(
                        {"error": "Invalid amount format"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        if "category_name" in payload:
            raw_category_name = str(payload.get("category_name") or "").strip()
            if raw_category_name:
                # Dashboard list may send labels like "🍔 Food"; normalize to "Food".
                category_name = raw_category_name
                if " " in category_name:
                    first_token, remainder = category_name.split(" ", 1)
                    if not any(ch.isalnum() for ch in first_token):
                        category_name = remainder.strip() or category_name

                try:
                    category = Category.objects.get(name__iexact=category_name)
                    transaction.category = category
                    transaction.category_name = category.name
                except Category.DoesNotExist:
                    # Keep backward compatibility with add endpoint: allow custom category names.
                    transaction.category = None
                    transaction.category_name = category_name

        if "transaction_date" in payload:
            raw_date = payload.get("transaction_date")
            if raw_date not in (None, ""):
                try:
                    transaction.transaction_date = datetime.fromisoformat(raw_date).date()
                except (ValueError, AttributeError, TypeError):
                    return Response(
                        {"error": "Invalid date format (use YYYY-MM-DD)"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        if "note" in payload:
            transaction.note = payload.get("note") or ""

        transaction.save()

        return Response(
            {
                "success": True,
                "message": "Transaction updated successfully",
                "updated": {
                    "id": transaction.id,
                    "amount": float(transaction.amount),
                    "category": transaction.category_name,
                    "date": transaction.transaction_date.isoformat(),
                    "note": transaction.note or "",
                },
            }
        )
    except Transaction.DoesNotExist:
        return Response(
            {"error": "Transaction not found or unauthorized"},
            status=status.HTTP_404_NOT_FOUND,
        )


class TransactionViewAPIView(SessionTelegramAPIMixin, APIView):
    """Dedicated class-based API for viewing transaction lists."""

    def get(self, request):
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        return _recent_transactions_response(request, telegram_id)


class TransactionAddAPIView(SessionTelegramAPIMixin, APIView):
    """Dedicated class-based API for adding transactions."""

    def post(self, request):
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        return _create_transaction_response(telegram_id, request.data)


class TransactionUpdateAPIView(SessionTelegramAPIMixin, APIView):
    """Dedicated class-based API for updating transactions."""

    def patch(self, request):
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        transaction_id = request.query_params.get("transaction_id")
        return _update_transaction_response(telegram_id, transaction_id, request.data)


class TransactionDeleteAPIView(SessionTelegramAPIMixin, APIView):
    """Dedicated class-based API for deleting transactions."""

    def delete(self, request):
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        transaction_id = request.query_params.get("transaction_id")
        return _delete_transaction_response(telegram_id, transaction_id)


class TransactionViewSet(viewsets.ModelViewSet):
    """API endpoints for financial transactions."""

    serializer_class = TransactionSerializer
    permission_classes = [AllowAny]

    def _session_telegram_id(self):
        telegram_id = self.request.session.get("telegram_id")
        if not telegram_id:
            return None
        try:
            return int(telegram_id)
        except (TypeError, ValueError):
            return None

    def _require_session_telegram_id(self):
        telegram_id = self._session_telegram_id()
        if telegram_id is None:
            return None, Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return telegram_id, None

    def get_queryset(self):
        """Filter transactions by current authenticated session user."""
        telegram_id = self._session_telegram_id()
        if telegram_id is not None:
            return Transaction.objects.filter(telegram_id=telegram_id)
        return Transaction.objects.none()

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get financial statistics for user."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error

        date_from, date_to = _parse_date_range(request)
        transactions = _filter_by_date(
            Transaction.objects.filter(telegram_id=telegram_id), date_from, date_to
        )

        total_income = (
            transactions.filter(transaction_type="income").aggregate(Sum("amount_usd"))[
                "amount_usd__sum"
            ]
            or 0
        )
        total_expenses = (
            transactions.filter(transaction_type="expense").aggregate(
                Sum("amount_usd")
            )["amount_usd__sum"]
            or 0
        )
        net = float(total_income) - float(total_expenses)
        transaction_count = transactions.count()

        # Monthly average
        months_count = (
            max(
                (
                    date.today()
                    - transactions.earliest("transaction_date").transaction_date
                ).days
                // 30,
                1,
            )
            if transactions.exists()
            else 1
        )
        monthly_average = float(total_expenses) / months_count

        KHR_RATE = _get_khr_rate_float()
        data = {
            "total_income": float(total_income),
            "total_expenses": float(total_expenses),
            "total_income_khr": float(total_income) * KHR_RATE,
            "total_expenses_khr": float(total_expenses) * KHR_RATE,
            "net": net,
            "net_khr": net * KHR_RATE,
            "transaction_count": transaction_count,
            "monthly_average": monthly_average,
            "monthly_average_khr": monthly_average * KHR_RATE,
        }

        serializer = StatisticsSerializer(data)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_category(self, request):
        """Get spending breakdown by category."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error

        KHR_RATE = _get_khr_rate_float()
        transactions = _filter_by_date(
            Transaction.objects.filter(
                telegram_id=telegram_id, transaction_type="expense"
            ),
            *_parse_date_range(request),
        )
        breakdown = (
            transactions.values("category__name", "category__icon")
            .annotate(total_amount=Sum("amount_usd"), count=Count("id"))
            .order_by("-total_amount")
        )

        # Format response
        result = [
            {
                "category": f"{item['category__icon']} {item['category__name']}",
                "total_amount": float(item["total_amount"] or 0),
                "total_amount_khr": float(item["total_amount"] or 0) * KHR_RATE,
                "count": item["count"],
            }
            for item in breakdown
        ]

        return Response(result)

    @action(detail=False, methods=["get"])
    def monthly_trend(self, request):
        """Get monthly spending trend."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error

        transactions = _filter_by_date(
            Transaction.objects.filter(telegram_id=telegram_id),
            *_parse_date_range(request),
        )

        # Group by month
        KHR_RATE = _get_khr_rate_float()
        monthly = (
            transactions.annotate(month=TruncMonth("transaction_date"))
            .values("month")
            .annotate(
                income=Sum("amount_usd", filter=Q(transaction_type="income")),
                expenses=Sum("amount_usd", filter=Q(transaction_type="expense")),
            )
            .order_by("month")
        )

        # Format for frontend
        result = [
            {
                "month": item["month"].strftime("%Y-%m") if item["month"] else "N/A",
                "income": float(item["income"] or 0),
                "expenses": float(item["expenses"] or 0),
                "income_khr": float(item["income"] or 0) * KHR_RATE,
                "expenses_khr": float(item["expenses"] or 0) * KHR_RATE,
            }
            for item in monthly
        ]

        return Response(result)

    @action(detail=False, methods=["get"])
    def recent(self, request):
        """Get recent transactions."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        return _recent_transactions_response(request, telegram_id)

    @action(detail=False, methods=["delete"])
    def delete_transaction(self, request):
        """Delete a transaction by ID."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        transaction_id = request.query_params.get("transaction_id")
        return _delete_transaction_response(telegram_id, transaction_id)

    @action(detail=False, methods=["post"])
    def add_transaction(self, request):
        """Create a new transaction from the dashboard quick-add form."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        return _create_transaction_response(telegram_id, request.data)

    @action(detail=False, methods=["patch"])
    def update_transaction(self, request):
        """Update a transaction by ID."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        transaction_id = request.query_params.get("transaction_id")
        return _update_transaction_response(telegram_id, transaction_id, request.data)

    @action(detail=False, methods=["get"])
    def categories(self, request):
        """Return list of all categories."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        cats = Category.objects.all().values_list("name", flat=True)
        return Response(list(cats))

    @action(detail=False, methods=["get"])
    def export_csv(self, request):
        """Export all transactions as CSV file."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error

        transactions = (
            Transaction.objects.filter(telegram_id=telegram_id)
            .select_related("category")
            .order_by("transaction_date")
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="transactions_{telegram_id}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Date",
                "Type",
                "Category",
                "Amount (USD)",
                "Amount (KHR)",
                "Currency",
                "Note",
            ]
        )

        KHR_RATE = _get_khr_rate_float()
        for t in transactions:
            amt_usd = float(t.amount_usd) if t.amount_usd else float(t.amount)
            amt_khr = float(t.amount_khr) if t.amount_khr else amt_usd * KHR_RATE
            cat = (
                f"{t.category.icon} {t.category.name}"
                if t.category
                else t.category_name
            )
            writer.writerow(
                [
                    t.transaction_date.isoformat(),
                    t.transaction_type,
                    cat,
                    f"{amt_usd:.2f}",
                    f"{amt_khr:.0f}",
                    t.currency or "USD",
                    t.note or "",
                ]
            )

        return response

    @action(detail=False, methods=["post"])
    def ai_chat(self, request):
        """AI financial advisor chat endpoint with text, image, and audio support."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        message = request.data.get("message", "").strip()
        image_base64 = request.data.get("image_base64", "")
        image_mime = request.data.get("image_mime", "image/jpeg")
        audio_base64 = request.data.get("audio_base64", "")
        audio_mime = request.data.get("audio_mime", "audio/webm")

        if not message and not image_base64 and not audio_base64:
            return Response(
                {"error": "message, image, or audio is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Gather user's financial context
        qs = Transaction.objects.filter(telegram_id=telegram_id)
        now = date.today()
        month_start = now.replace(day=1)

        total_income = (
            qs.filter(transaction_type="income").aggregate(s=Sum("amount_usd"))["s"]
            or 0
        )
        total_expense = (
            qs.filter(transaction_type="expense").aggregate(s=Sum("amount_usd"))["s"]
            or 0
        )
        month_income = (
            qs.filter(
                transaction_type="income", transaction_date__gte=month_start
            ).aggregate(s=Sum("amount_usd"))["s"]
            or 0
        )
        month_expense = (
            qs.filter(
                transaction_type="expense", transaction_date__gte=month_start
            ).aggregate(s=Sum("amount_usd"))["s"]
            or 0
        )
        tx_count = qs.count()

        # Top categories this month
        top_cats = (
            qs.filter(transaction_type="expense", transaction_date__gte=month_start)
            .values("category_name")
            .annotate(total=Sum("amount_usd"))
            .order_by("-total")[:5]
        )
        cat_summary = (
            ", ".join(
                f"{c['category_name']}: ${float(c['total']):.2f}" for c in top_cats
            )
            or "No expenses yet"
        )

        # Recent 5 transactions
        recent = qs.order_by("-transaction_date", "-id")[:5]
        recent_summary = (
            "; ".join(
                f"{t.transaction_type} ${float(t.amount_usd):.2f} ({t.category_name}, {t.transaction_date})"
                for t in recent
            )
            or "No transactions"
        )

        context_prompt = (
            f"USER FINANCIAL CONTEXT:\n"
            f"- All-time: Income ${float(total_income):.2f}, Expenses ${float(total_expense):.2f}, "
            f"Balance ${float(total_income - total_expense):.2f}\n"
            f"- This month ({now.strftime('%B %Y')}): Income ${float(month_income):.2f}, "
            f"Expenses ${float(month_expense):.2f}\n"
            f"- Total transactions: {tx_count}\n"
            f"- Top expense categories this month: {cat_summary}\n"
            f"- Recent transactions: {recent_summary}\n"
            f"- Current exchange rate: 1 USD ≈ {_get_khr_rate_float():,.0f} KHR\n\n"
            f"USER QUESTION: {message}"
        )

        import os

        import google.generativeai as genai
        from dotenv import load_dotenv

        load_dotenv()

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return Response(
                {"error": "AI service not configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        genai.configure(api_key=api_key)

        current_rate = _get_khr_rate_float()

        system_prompt = (
            "You are a friendly, expert financial advisor AI assistant for a personal finance app. "
            "You have access to the user's financial data provided below. "
            "IMPORTANT: Detect the user's language. If they write in Khmer (ខ្មែរ), reply in Khmer. "
            "If in English, reply in English. Always match the user's language.\n\n"
            "Your capabilities:\n"
            "1. Answer any financial questions (budgeting, saving, investing, debt)\n"
            "2. Analyze the user's spending patterns and give personalized advice\n"
            "3. Suggest ways to save money based on their actual data\n"
            "4. Help with financial planning and goal setting\n"
            "5. Explain financial concepts in simple terms\n"
            "6. Give motivational financial tips\n"
            "7. READ RECEIPTS/INVOICES from photos: extract items, prices, totals, store name, date\n"
            "8. LISTEN TO VOICE MESSAGES: transcribe and understand audio, then respond naturally\n\n"
            "When you receive a voice message/audio:\n"
            "- First transcribe what the user said\n"
            "- Then respond to their question or request naturally\n"
            "- If the audio is unclear, ask for clarification politely\n\n"
            "When you receive a receipt/invoice image:\n"
            "- List all items with their prices\n"
            "- Show the total amount\n"
            "- Identify the store/vendor name and date if visible\n"
            "- Suggest which expense category each item belongs to\n"
            "- Summarize in the user's language\n\n"
            "Rules:\n"
            "- Be concise but helpful (2-4 paragraphs max)\n"
            "- Use emojis to make responses friendly\n"
            "- Reference the user's actual financial data when relevant\n"
            "- Give specific, actionable advice\n"
            f"- Current exchange rate: 1 USD ≈ {current_rate:,.0f} KHR\n"
            "- If the question is not finance-related, politely redirect to financial topics\n"
        )

        candidate_models = [
            "models/gemini-2.5-flash",
            "models/gemini-2.0-flash",
            "models/gemini-2.5-flash-lite",
        ]

        import base64
        import time

        response_obj = None
        last_exc = None

        # Build content parts (text + optional image/audio)
        content_parts = []
        if audio_base64:
            try:
                audio_bytes = base64.b64decode(audio_base64)
                content_parts.append(
                    {
                        "mime_type": audio_mime,
                        "data": audio_bytes,
                    }
                )
                if not message:
                    message = "Please listen to this voice message and respond helpfully. Transcribe what was said and answer accordingly."
            except Exception:
                pass
        content_parts.append(context_prompt)
        if image_base64:
            try:
                image_bytes = base64.b64decode(image_base64)
                content_parts.append(
                    {
                        "mime_type": image_mime,
                        "data": image_bytes,
                    }
                )
            except Exception:
                pass  # Skip invalid base64, still send text

        for attempt in range(2):
            for mname in candidate_models:
                try:
                    model = genai.GenerativeModel(
                        mname, system_instruction=system_prompt
                    )
                    response_obj = model.generate_content(content_parts)
                    break
                except Exception as e:
                    last_exc = e
            if response_obj is not None:
                break
            if attempt == 0:
                time.sleep(2)

        # Always save user message
        conversation_id = request.data.get("conversation_id")
        if conversation_id:
            import uuid

            try:
                conversation_id = uuid.UUID(conversation_id)
            except ValueError:
                conversation_id = uuid.uuid4()
        else:
            import uuid

            conversation_id = uuid.uuid4()

        ChatMessage.objects.create(
            telegram_id=telegram_id,
            conversation_id=conversation_id,
            role="user",
            message=(
                "[🎤 Voice] " if audio_base64 else "[📷 Image] " if image_base64 else ""
            )
            + message,
        )

        if response_obj is None:
            err = str(last_exc)[:200] if last_exc else "unknown"
            if "429" in err or "quota" in err.lower():
                busy_msg = "⏳ AI រវល់បណ្តោះអាសន្ន។ សូមព្យាយាមម្តងទៀត។\nAI is busy. Please try again shortly."
                ChatMessage.objects.create(
                    telegram_id=telegram_id,
                    conversation_id=conversation_id,
                    role="ai",
                    message=busy_msg,
                )
                return Response(
                    {"reply": busy_msg, "conversation_id": str(conversation_id)}
                )
            error_msg = f"❌ AI error: {err}"
            ChatMessage.objects.create(
                telegram_id=telegram_id,
                conversation_id=conversation_id,
                role="ai",
                message=error_msg,
            )
            return Response(
                {"error": error_msg, "conversation_id": str(conversation_id)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Save AI reply
        ChatMessage.objects.create(
            telegram_id=telegram_id,
            conversation_id=conversation_id,
            role="ai",
            message=response_obj.text,
        )

        return Response(
            {"reply": response_obj.text, "conversation_id": str(conversation_id)}
        )

    @action(detail=False, methods=["get"])
    def chat_history(self, request):
        """Get chat history for a conversation."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        conversation_id = request.query_params.get("conversation_id")

        qs = ChatMessage.objects.filter(telegram_id=telegram_id)
        if conversation_id:
            qs = qs.filter(conversation_id=conversation_id)
        messages = qs.order_by("created_at")[:200]
        data = [
            {
                "role": m.role,
                "message": m.message,
                "created_at": m.created_at.isoformat(),
                "conversation_id": str(m.conversation_id),
            }
            for m in messages
        ]
        return Response({"messages": data})

    @action(detail=False, methods=["get"])
    def chat_conversations(self, request):
        """List all conversations for a user."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error

        from django.db.models import Max, Min

        convos = (
            ChatMessage.objects.filter(telegram_id=telegram_id)
            .values("conversation_id")
            .annotate(
                last_message_at=Max("created_at"),
                first_message_at=Min("created_at"),
            )
            .order_by("-last_message_at")
        )
        data = []
        for c in convos:
            # Get first user message as preview
            first_msg = ChatMessage.objects.filter(
                telegram_id=telegram_id,
                conversation_id=c["conversation_id"],
                role="user",
            ).first()
            data.append(
                {
                    "conversation_id": str(c["conversation_id"]),
                    "preview": first_msg.message[:60] if first_msg else "New chat",
                    "last_message_at": c["last_message_at"].isoformat(),
                    "first_message_at": c["first_message_at"].isoformat(),
                }
            )
        return Response({"conversations": data})

    @action(detail=False, methods=["post"])
    def clear_chat(self, request):
        """Delete a specific conversation or all chats."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        conversation_id = request.data.get("conversation_id")

        qs = ChatMessage.objects.filter(telegram_id=telegram_id)
        if conversation_id:
            qs = qs.filter(conversation_id=conversation_id)
        count, _ = qs.delete()
        return Response({"deleted": count})
