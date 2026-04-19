from django.db import models
from django.utils import timezone
import hashlib
import hmac
import secrets
import string
import uuid


class OTPSession(models.Model):
    """Store OTP sessions for phone-based authentication."""
    phone_number = models.CharField(max_length=20)
    otp_code = models.CharField(max_length=6)
    telegram_id = models.BigIntegerField(null=True, blank=True)  # Linked after verification
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    attempt_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"OTP for {self.phone_number}"

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_valid(self):
        return not self.is_expired() and not self.is_verified and self.attempt_count < 5

    @staticmethod
    def generate_otp():
        """Generate a 6-digit OTP."""
        return ''.join(secrets.choice(string.digits) for _ in range(6))


class TelegramUser(models.Model):
    """User linked to Telegram for authentication."""
    telegram_id = models.BigIntegerField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    username = models.CharField(max_length=150, blank=True, null=True)
    photo_url = models.URLField(blank=True, null=True)
    auth_date = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Telegram User {self.telegram_id}"

    @staticmethod
    def verify_telegram_hash(data_dict, bot_token):
        """Verify the hash from Telegram login widget data."""
        secret_key = hashlib.sha256(bot_token.encode()).digest()
        hash_value = data_dict.pop('hash', '')
        
        # Sort keys and create data check string
        data_check = '\n'.join([f"{k}={v}" for k, v in sorted(data_dict.items())])
        
        # Compute HMAC-SHA256
        expected_hash = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
        
        return hash_value == expected_hash

class Category(models.Model):
    """Spending categories like Food, Transport, Bills, etc."""
    name = models.CharField(max_length=50, unique=True)
    icon = models.CharField(max_length=10, default="💰")  # emoji icon
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Categories"

    def __str__(self):
        return f"{self.icon} {self.name}"

class Transaction(models.Model):
    """Financial transaction record."""
    TRANSACTION_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('KHR', 'Cambodian Riel'),
    ]

    telegram_id = models.BigIntegerField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    amount_usd = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    amount_khr = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    category_name = models.CharField(max_length=100, default='Other')  # fallback if category deleted
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    
    note = models.TextField(null=True, blank=True)
    transaction_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Metadata for analytics
    is_recurring = models.BooleanField(default=False)
    tags = models.CharField(max_length=200, blank=True)  # comma-separated tags
    
    class Meta:
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['telegram_id', '-transaction_date']),
            models.Index(fields=['telegram_id', 'transaction_type']),
        ]

    def __str__(self):
        return f"{self.transaction_type.capitalize()}: ${self.amount} ({self.category_name})"

class Budget(models.Model):
    """Budget tracking for categories."""
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    telegram_id = models.BigIntegerField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    limit_amount = models.DecimalField(max_digits=15, decimal_places=2)
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='monthly')
    
    # Alert settings
    alert_threshold = models.IntegerField(default=80, help_text="Alert when % of budget is spent")
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('telegram_id', 'category', 'frequency')
        ordering = ['category__name']

    def __str__(self):
        return f"Budget: {self.category} - ${self.limit_amount}/{self.frequency}"
    
    def get_spent_amount(self):
        """Calculate spent amount for this budget period."""
        from django.utils.timezone import now
        from datetime import timedelta
        
        today = now().date()
        
        if self.frequency == 'daily':
            start_date = today
        elif self.frequency == 'weekly':
            start_date = today - timedelta(days=today.weekday())
        elif self.frequency == 'monthly':
            start_date = today.replace(day=1)
        else:  # yearly
            start_date = today.replace(month=1, day=1)
        
        spent = Transaction.objects.filter(
            telegram_id=self.telegram_id,
            category=self.category,
            transaction_type='expense',
            transaction_date__gte=start_date
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0
        
        return spent
    
    def get_percentage_used(self):
        """Get percentage of budget used."""
        spent = self.get_spent_amount()
        return (float(spent) / float(self.limit_amount) * 100) if self.limit_amount else 0
    
    def is_exceeded(self):
        """Check if budget is exceeded."""
        return self.get_percentage_used() >= 100


class ChatMessage(models.Model):
    """Store AI chat history per user."""
    ROLE_CHOICES = [
        ('user', 'User'),
        ('ai', 'AI'),
    ]
    telegram_id = models.BigIntegerField()
    conversation_id = models.UUIDField(default=uuid.uuid4)
    role = models.CharField(max_length=4, choices=ROLE_CHOICES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['telegram_id', 'created_at']),
            models.Index(fields=['telegram_id', 'conversation_id']),
        ]

    def __str__(self):
        return f"{self.role}: {self.message[:50]}"
        return self.get_percentage_used() > 100