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
    total_income = serializers.FloatField()
    total_expenses = serializers.FloatField()
    total_income_khr = serializers.FloatField()
    total_expenses_khr = serializers.FloatField()
    net = serializers.FloatField()
    net_khr = serializers.FloatField()
    transaction_count = serializers.IntegerField()
    monthly_average = serializers.FloatField()
    monthly_average_khr = serializers.FloatField()
