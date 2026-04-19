from django.db import models
from django.utils import timezone

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

    telegram_id = models.BigIntegerField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
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
        return self.get_percentage_used() > 100