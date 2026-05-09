"""API views for the finance tracker app."""

import csv
import logging
import math
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

logger = logging.getLogger(__name__)

from tracker.authz import can_write, role_for_telegram_id
from tracker.models import (
    Budget,
    Category,
    ChatMessage,
    ChatMessageRevision,
    TelegramUser,
    Transaction,
)
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


def _parse_pagination(request):
    """Parse page/page_size query params with safe defaults."""
    try:
        page = max(int(request.query_params.get("page", 1)), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.query_params.get("page_size", 20))
    except (TypeError, ValueError):
        page_size = 20
    page_size = min(max(page_size, 1), 100)
    return page, page_size


def _paginate_queryset(request, queryset):
    """Return paginated slice + metadata."""
    page, page_size = _parse_pagination(request)
    total_count = queryset.count()
    total_pages = max(math.ceil(total_count / page_size), 1)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * page_size
    end = start + page_size
    return queryset[start:end], {
        "count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


def _serialize_transaction_item(tx, khr_rate: float):
    """Serialize transaction row for SPA tables."""
    amt_usd = float(tx.amount_usd) if tx.amount_usd else float(tx.amount)
    amt_khr = float(tx.amount_khr) if tx.amount_khr else amt_usd * khr_rate
    category_label = f"{tx.category.icon} {tx.category.name}" if tx.category else tx.category_name
    return {
        "id": tx.id,
        "amount": float(tx.amount),
        "amount_usd": amt_usd,
        "amount_khr": amt_khr,
        "amount_display": f"${amt_usd:,.2f}",
        "currency": tx.currency or "USD",
        "type": tx.transaction_type,
        "category": category_label,
        "description": tx.note or "",
        "date": tx.transaction_date.isoformat(),
        "created_at": tx.created_at.isoformat(),
        "user": str(tx.telegram_id),
    }


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

    def _session_role(self):
        return role_for_telegram_id(self._session_telegram_id())

    def _require_write_role(self):
        role = self._session_role()
        if not can_write(role):
            return Response(
                {"error": "Insufficient role for write operation", "role": role},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None


def _recent_transactions_response(request, telegram_id: int):
    """Build recent/view transactions response."""
    try:
        limit = int(request.query_params.get("limit", 20))
    except (TypeError, ValueError):
        limit = 20
    limit = min(max(limit, 1), 100)
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
        result.append(_serialize_transaction_item(tx, khr_rate))
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
        role_error = self._require_write_role()
        if role_error:
            return role_error
        return _create_transaction_response(telegram_id, request.data)


class TransactionUpdateAPIView(SessionTelegramAPIMixin, APIView):
    """Dedicated class-based API for updating transactions."""

    def patch(self, request):
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        role_error = self._require_write_role()
        if role_error:
            return role_error
        transaction_id = request.query_params.get("transaction_id")
        return _update_transaction_response(telegram_id, transaction_id, request.data)


class TransactionDeleteAPIView(SessionTelegramAPIMixin, APIView):
    """Dedicated class-based API for deleting transactions."""

    def delete(self, request):
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        role_error = self._require_write_role()
        if role_error:
            return role_error
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
            return Transaction.objects.filter(telegram_id=telegram_id).select_related("category")
        return Transaction.objects.none()

    def list(self, request, *args, **kwargs):
        """List transactions with pagination, filtering, and sorting for SPA tables."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error

        queryset = Transaction.objects.filter(telegram_id=telegram_id).select_related("category")

        tx_type = (request.query_params.get("type") or "").strip().lower()
        if tx_type in {"income", "expense"}:
            queryset = queryset.filter(transaction_type=tx_type)

        category = (request.query_params.get("category") or "").strip()
        if category:
            queryset = queryset.filter(
                Q(category_name__icontains=category) | Q(category__name__icontains=category)
            )

        search = (request.query_params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(note__icontains=search)
                | Q(category_name__icontains=search)
                | Q(transaction_type__icontains=search)
                | Q(tags__icontains=search)
            )

        date_from, date_to = _parse_date_range(request)
        queryset = _filter_by_date(queryset, date_from, date_to)

        sort_map = {
            "date": "transaction_date",
            "amount": "amount_usd",
            "created_at": "created_at",
            "category": "category_name",
            "type": "transaction_type",
        }
        sort_by = sort_map.get((request.query_params.get("sort_by") or "date").lower(), "transaction_date")
        sort_order = (request.query_params.get("sort_order") or "desc").lower()
        order_prefix = "" if sort_order == "asc" else "-"
        queryset = queryset.order_by(f"{order_prefix}{sort_by}", "-created_at")

        page_items, page_meta = _paginate_queryset(request, queryset)
        khr_rate = _get_khr_rate_float()
        results = [_serialize_transaction_item(tx, khr_rate) for tx in page_items]
        return Response({"results": results, **page_meta})

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
        if not can_write(role_for_telegram_id(telegram_id)):
            return Response({"error": "Insufficient role for write operation"}, status=status.HTTP_403_FORBIDDEN)
        transaction_id = request.query_params.get("transaction_id")
        return _delete_transaction_response(telegram_id, transaction_id)

    @action(detail=False, methods=["post"])
    def add_transaction(self, request):
        """Create a new transaction from the dashboard quick-add form."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        if not can_write(role_for_telegram_id(telegram_id)):
            return Response({"error": "Insufficient role for write operation"}, status=status.HTTP_403_FORBIDDEN)
        return _create_transaction_response(telegram_id, request.data)

    @action(detail=False, methods=["patch"])
    def update_transaction(self, request):
        """Update a transaction by ID."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        if not can_write(role_for_telegram_id(telegram_id)):
            return Response({"error": "Insufficient role for write operation"}, status=status.HTTP_403_FORBIDDEN)
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

    def _generate_ai_reply_text(
        self,
        telegram_id: int,
        message: str,
        image_base64: str = "",
        image_mime: str = "image/jpeg",
        audio_base64: str = "",
        audio_mime: str = "audio/webm",
    ):
        """Generate an AI reply from message + optional image/audio."""
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

        import base64
        import os
        import time

        try:
            import google.generativeai as genai
        except ModuleNotFoundError as exc:
            raise RuntimeError("AI SDK missing on server (google-generativeai not installed)") from exc
        from dotenv import load_dotenv

        load_dotenv()
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("AI service not configured")

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
            "models/gemini-2.5-flash-lite",
            "models/gemini-2.0-flash",
            "models/gemini-1.5-flash",
            "models/gemini-1.5-flash-8b",
        ]

        content_parts = []
        if audio_base64:
            try:
                content_parts.append(
                    {
                        "mime_type": audio_mime,
                        "data": base64.b64decode(audio_base64),
                    }
                )
            except Exception:
                pass
        content_parts.append(context_prompt)
        if image_base64:
            try:
                content_parts.append(
                    {
                        "mime_type": image_mime,
                        "data": base64.b64decode(image_base64),
                    }
                )
            except Exception:
                pass

        response_obj = None
        last_exc = None
        for attempt in range(2):
            for mname in candidate_models:
                try:
                    model = genai.GenerativeModel(mname, system_instruction=system_prompt)
                    response_obj = model.generate_content(content_parts)
                    break
                except Exception as e:
                    last_exc = e
            if response_obj is not None:
                break
            if attempt == 0:
                time.sleep(2)

        if response_obj is None:
            raise RuntimeError(str(last_exc) if last_exc else "AI generation failed")
        return response_obj.text

    @action(detail=False, methods=["post"])
    def ai_chat(self, request):
        """AI financial advisor chat endpoint with text, image, and audio support."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        message = request.data.get("message", "").strip()
        user_display_message = message
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

        try:
            import google.generativeai as genai
        except ModuleNotFoundError:
            return Response(
                {"error": "AI SDK missing on server. Please redeploy after installing dependencies."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
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
            "models/gemini-2.5-flash-lite",
            "models/gemini-2.0-flash",
            "models/gemini-1.5-flash",
            "models/gemini-1.5-flash-8b",
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
                    logger.error(f"[Gemini API] Model {mname} failed (attempt {attempt+1}): {type(e).__name__}: {str(e)[:300]}", exc_info=True)
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
            + user_display_message,
            image_base64=image_base64 or None,
            image_mime=image_mime or None,
            audio_base64=audio_base64 or None,
            audio_mime=audio_mime or None,
        )

        if response_obj is None:
            err = str(last_exc)[:200] if last_exc else "unknown"
            logger.error(f"[Gemini API] All attempts failed for user {telegram_id}: {err}")
            err_lc = err.lower()
            if "location is not supported" in err_lc or "user location" in err_lc:
                blocked_msg = (
                    "⚠️ AI chat is temporarily unavailable in this deployment region.\n"
                    "សេវា AI មិនអាចប្រើបានបណ្ដោះអាសន្នតាមតំបន់ server នេះ។\n\n"
                    "You can still record transactions normally (income/expense, summary, balance)."
                )
                ChatMessage.objects.create(
                    telegram_id=telegram_id,
                    conversation_id=conversation_id,
                    role="ai",
                    message=blocked_msg,
                )
                return Response(
                    {"reply": blocked_msg, "conversation_id": str(conversation_id)}
                )
            if (
                "not found for api version" in err_lc
                or "not supported for generatecontent" in err_lc
                or "model" in err_lc and "not found" in err_lc
            ):
                model_msg = (
                    "⚠️ AI model is temporarily unavailable on this deployment.\n"
                    "ម៉ូឌែល AI មិនអាចប្រើបានបណ្ដោះអាសន្នលើ server នេះ។\n\n"
                    "Please try again in a moment."
                )
                ChatMessage.objects.create(
                    telegram_id=telegram_id,
                    conversation_id=conversation_id,
                    role="ai",
                    message=model_msg,
                )
                return Response(
                    {"reply": model_msg, "conversation_id": str(conversation_id)}
                )
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
                "id": m.id,
                "role": m.role,
                "message": m.message,
                "image_base64": m.image_base64,
                "image_mime": m.image_mime,
                "audio_base64": m.audio_base64,
                "audio_mime": m.audio_mime,
                "created_at": m.created_at.isoformat(),
                "conversation_id": str(m.conversation_id),
                "revisions": [
                    {
                        "id": rv.id,
                        "old_message": rv.old_message,
                        "new_message": rv.new_message,
                        "action": rv.action,
                        "created_at": rv.created_at.isoformat(),
                    }
                    for rv in m.revisions.all().order_by("created_at")
                ],
            }
            for m in messages
        ]
        return Response({"messages": data})

    @action(detail=False, methods=["patch"])
    def update_chat_message(self, request):
        """Update a single user chat message text in history."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        if not can_write(role_for_telegram_id(telegram_id)):
            return Response({"error": "Insufficient role for write operation"}, status=status.HTTP_403_FORBIDDEN)

        message_id = request.data.get("message_id")
        new_message = (request.data.get("message") or "").strip()
        if not message_id:
            return Response({"error": "message_id required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            msg = ChatMessage.objects.get(
                id=message_id,
                telegram_id=telegram_id,
                role="user",
            )
        except ChatMessage.DoesNotExist:
            return Response({"error": "Message not found"}, status=status.HTTP_404_NOT_FOUND)

        original = msg.message or ""
        prefix = ""
        if original.startswith("[🎤 Voice]"):
            prefix = "[🎤 Voice] "
        elif original.startswith("[📷 Image]"):
            prefix = "[📷 Image] "

        # Allow empty text only when media exists; otherwise require text.
        if not new_message and not (msg.image_base64 or msg.audio_base64):
            return Response({"error": "message is required"}, status=status.HTTP_400_BAD_REQUEST)

        old_message = msg.message
        new_full_message = (prefix + new_message).strip() if new_message else prefix.strip()

        if old_message != new_full_message:
            ChatMessageRevision.objects.create(
                chat_message=msg,
                telegram_id=telegram_id,
                old_message=old_message,
                new_message=new_full_message,
                action="edit",
            )

        msg.message = new_full_message
        msg.save(update_fields=["message"])

        regenerate = bool(request.data.get("regenerate"))
        ai_text = None
        if regenerate:
            effective_text = new_message
            if not effective_text:
                effective_text = (
                    "Please listen to this voice message and respond helpfully. Transcribe what was said and answer accordingly."
                    if msg.audio_base64
                    else "Please read this receipt and tell me the details (items, prices, total)"
                    if msg.image_base64
                    else ""
                )
            try:
                ai_text = self._generate_ai_reply_text(
                    telegram_id=telegram_id,
                    message=effective_text,
                    image_base64=msg.image_base64 or "",
                    image_mime=msg.image_mime or "image/jpeg",
                    audio_base64=msg.audio_base64 or "",
                    audio_mime=msg.audio_mime or "audio/webm",
                )
            except Exception as e:
                return Response(
                    {"error": f"Failed to regenerate AI reply: {str(e)[:200]}"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            next_ai = (
                ChatMessage.objects.filter(
                    telegram_id=telegram_id,
                    conversation_id=msg.conversation_id,
                    role="ai",
                    created_at__gt=msg.created_at,
                )
                .order_by("created_at")
                .first()
            )
            if next_ai:
                ChatMessageRevision.objects.create(
                    chat_message=next_ai,
                    telegram_id=telegram_id,
                    old_message=next_ai.message,
                    new_message=ai_text,
                    action="regenerate",
                )
                # Keep the old AI reply in the timeline and append the regenerated one.
                ChatMessage.objects.create(
                    telegram_id=telegram_id,
                    conversation_id=msg.conversation_id,
                    role="ai",
                    message=ai_text,
                )
            else:
                ChatMessage.objects.create(
                    telegram_id=telegram_id,
                    conversation_id=msg.conversation_id,
                    role="ai",
                    message=ai_text,
                )

        return Response(
            {
                "success": True,
                "message_id": msg.id,
                "message": msg.message,
                "ai_reply": ai_text,
            }
        )

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
            if first_msg:
                preview = first_msg.message[:60]
                if first_msg.audio_base64:
                    preview = "🎤 " + (preview or "Voice message")
                elif first_msg.image_base64:
                    preview = "📷 " + (preview or "Receipt/Photo")
                preview = preview[:60]
            else:
                preview = "New chat"
            data.append(
                {
                    "conversation_id": str(c["conversation_id"]),
                    "first_message_id": first_msg.id if first_msg else None,
                    "preview": preview,
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
        if not can_write(role_for_telegram_id(telegram_id)):
            return Response({"error": "Insufficient role for write operation"}, status=status.HTTP_403_FORBIDDEN)
        conversation_id = request.data.get("conversation_id")

        qs = ChatMessage.objects.filter(telegram_id=telegram_id)
        if conversation_id:
            qs = qs.filter(conversation_id=conversation_id)
        count, _ = qs.delete()
        return Response({"deleted": count})

    @action(detail=False, methods=["post"])
    def delete_chat_message(self, request):
        """Delete one user message and optionally its paired AI reply."""
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error
        if not can_write(role_for_telegram_id(telegram_id)):
            return Response({"error": "Insufficient role for write operation"}, status=status.HTTP_403_FORBIDDEN)

        message_id = request.data.get("message_id")
        with_pair = bool(request.data.get("with_pair", True))
        if not message_id:
            return Response({"error": "message_id required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user_msg = ChatMessage.objects.get(
                id=message_id,
                telegram_id=telegram_id,
                role="user",
            )
        except ChatMessage.DoesNotExist:
            return Response({"error": "Message not found"}, status=status.HTTP_404_NOT_FOUND)

        deleted = 0
        convo_id = user_msg.conversation_id
        created_at = user_msg.created_at
        user_msg.delete()
        deleted += 1

        if with_pair:
            next_ai = (
                ChatMessage.objects.filter(
                    telegram_id=telegram_id,
                    conversation_id=convo_id,
                    role="ai",
                    created_at__gt=created_at,
                )
                .order_by("created_at")
                .first()
            )
            if next_ai:
                next_ai.delete()
                deleted += 1

        return Response({"success": True, "deleted": deleted})


class UserListAPIView(SessionTelegramAPIMixin, APIView):
    """List Telegram users for admin SPA table with pagination/filter/sort."""

    def get(self, request):
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error

        if role_for_telegram_id(telegram_id) != "admin":
            return Response({"error": "Admin role required"}, status=status.HTTP_403_FORBIDDEN)

        queryset = TelegramUser.objects.all()
        search = (request.query_params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(username__icontains=search)
                | Q(phone_number__icontains=search)
            )

        sort_map = {
            "created_at": "created_at",
            "username": "username",
            "telegram_id": "telegram_id",
        }
        sort_by = sort_map.get((request.query_params.get("sort_by") or "created_at").lower(), "created_at")
        sort_order = (request.query_params.get("sort_order") or "desc").lower()
        queryset = queryset.order_by(("" if sort_order == "asc" else "-") + sort_by)

        page_items, page_meta = _paginate_queryset(request, queryset)
        results = [
            {
                "id": item.id,
                "telegram_id": item.telegram_id,
                "name": f"{item.first_name or ''} {item.last_name or ''}".strip() or item.username or str(item.telegram_id),
                "username": item.username or "",
                "phone": item.phone_number or "",
                "role": role_for_telegram_id(item.telegram_id),
                "created_at": item.created_at.isoformat(),
            }
            for item in page_items
        ]
        return Response({"results": results, **page_meta})


class BudgetListAPIView(SessionTelegramAPIMixin, APIView):
    """List budgets for current user with pagination/filter/sort."""

    def get(self, request):
        telegram_id, error = self._require_session_telegram_id()
        if error:
            return error

        queryset = Budget.objects.filter(telegram_id=telegram_id).select_related("category")
        search = (request.query_params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(category__name__icontains=search)

        sort_map = {
            "category": "category__name",
            "limit": "limit_amount",
            "frequency": "frequency",
            "created_at": "created_at",
        }
        sort_by = sort_map.get((request.query_params.get("sort_by") or "category").lower(), "category__name")
        sort_order = (request.query_params.get("sort_order") or "asc").lower()
        queryset = queryset.order_by(("" if sort_order == "asc" else "-") + sort_by)

        page_items, page_meta = _paginate_queryset(request, queryset)
        results = []
        for item in page_items:
            spent = float(item.get_spent_amount())
            limit_amount = float(item.limit_amount)
            pct = item.get_percentage_used()
            results.append(
                {
                    "id": item.id,
                    "category": f"{item.category.icon} {item.category.name}",
                    "frequency": item.frequency,
                    "limit_amount": limit_amount,
                    "spent_amount": spent,
                    "percentage_used": round(pct, 2),
                    "status": "over" if pct >= 100 else "safe",
                    "alert_threshold": item.alert_threshold,
                    "is_active": item.is_active,
                }
            )

        return Response({"results": results, **page_meta})
