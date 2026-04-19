# tracker/views_api.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from datetime import timedelta, date
from django.shortcuts import render
from tracker.models import Transaction
from tracker.serializers import TransactionSerializer, TransactionListSerializer, StatisticsSerializer


def dashboard_view(request):
    """Render the dashboard template."""
    return render(request, 'dashboard.html')


class TransactionViewSet(viewsets.ModelViewSet):
    """API endpoints for financial transactions."""
    serializer_class = TransactionSerializer
    
    def get_queryset(self):
        """Filter transactions by current user (telegram_id from query params)."""
        telegram_id = self.request.query_params.get('telegram_id')
        if telegram_id:
            return Transaction.objects.filter(telegram_id=telegram_id)
        return Transaction.objects.none()
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get financial statistics for user."""
        telegram_id = request.query_params.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        transactions = Transaction.objects.filter(telegram_id=telegram_id)
        
        total_income = transactions.filter(transaction_type='income').aggregate(Sum('amount'))['amount__sum'] or 0
        total_expenses = transactions.filter(transaction_type='expense').aggregate(Sum('amount'))['amount__sum'] or 0
        net = total_income - total_expenses
        transaction_count = transactions.count()
        
        # Monthly average
        months_count = max((date.today() - transactions.earliest('transaction_date').transaction_date).days // 30, 1) if transactions.exists() else 1
        monthly_average = total_expenses / months_count
        
        data = {
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net': net,
            'transaction_count': transaction_count,
            'monthly_average': monthly_average,
        }
        
        serializer = StatisticsSerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Get spending breakdown by category."""
        telegram_id = request.query_params.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        transactions = Transaction.objects.filter(telegram_id=telegram_id, transaction_type='expense')
        breakdown = transactions.values('category__name', 'category__icon').annotate(
            total_amount=Sum('amount'), 
            count=Count('id')
        ).order_by('-total_amount')
        
        # Format response
        result = [
            {
                'category': f"{item['category__icon']} {item['category__name']}",
                'total_amount': float(item['total_amount']),
                'count': item['count']
            }
            for item in breakdown
        ]
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def monthly_trend(self, request):
        """Get monthly spending trend."""
        telegram_id = request.query_params.get('telegram_id')
        if not telegram_id:
            return Response({'error': 'telegram_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        transactions = Transaction.objects.filter(telegram_id=telegram_id)
        
        # Group by month
        monthly = transactions.annotate(month=TruncMonth('transaction_date')).values('month').annotate(
            income=Sum('amount', filter=Q(transaction_type='income')),
            expenses=Sum('amount', filter=Q(transaction_type='expense')),
        ).order_by('month')
        
        # Format for frontend
        result = [
            {
                'month': item['month'].strftime('%Y-%m') if item['month'] else 'N/A',
                'income': float(item['income'] or 0),
                'expenses': float(item['expenses'] or 0)
            }
            for item in monthly
        ]
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent transactions."""
        telegram_id = request.query_params.get('telegram_id')
        limit = int(request.query_params.get('limit', 20))
        
        if not telegram_id:
            return Response({'error': 'telegram_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        transactions = Transaction.objects.filter(telegram_id=telegram_id).select_related('category').order_by('-transaction_date')[:limit]
        
        result = []
        for t in transactions:
            result.append({
                'id': t.id,
                'amount': float(t.amount),
                'type': t.transaction_type,
                'category': f"{t.category.icon} {t.category.name}" if t.category else t.category_name,
                'description': t.note or '',
                'date': t.transaction_date.isoformat(),
                'created_at': t.created_at.isoformat()
            })
        
        return Response(result)
