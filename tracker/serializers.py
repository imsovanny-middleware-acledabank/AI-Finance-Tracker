# tracker/serializers.py
from rest_framework import serializers
from tracker.models import Transaction

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'telegram_id', 'amount', 'category', 'transaction_type', 'note', 'transaction_date', 'created_at']
        read_only_fields = ['id', 'created_at']

class TransactionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'amount', 'category', 'transaction_type', 'note', 'transaction_date']

class StatisticsSerializer(serializers.Serializer):
    total_income = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=15, decimal_places=2)
    net = serializers.DecimalField(max_digits=15, decimal_places=2)
    transaction_count = serializers.IntegerField()
    monthly_average = serializers.DecimalField(max_digits=15, decimal_places=2)
