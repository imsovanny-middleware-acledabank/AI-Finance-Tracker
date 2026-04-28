#!/usr/bin/env python
"""Script to populate test data for the finance tracker app."""

import os
from datetime import date, timedelta
from decimal import Decimal

import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from tracker.models import Category, Transaction

# Create test categories
categories_data = [
    ("Food", "🍔"),
    ("Transport", "🚗"),
    ("Entertainment", "🎬"),
    ("Shopping", "🛍️"),
    ("Bills", "💡"),
    ("Health", "💊"),
    ("Salary", "💰"),
]

categories = {}
for name, icon in categories_data:
    cat, created = Category.objects.get_or_create(name=name, defaults={"icon": icon})
    categories[name] = cat
    if created:
        print(f"Created category: {name} {icon}")

# Clear old test transactions
Transaction.objects.filter(telegram_id="123").delete()

# Create test transactions
test_data = [
    # Income
    {
        "telegram_id": "123",
        "amount": Decimal("5000.00"),
        "transaction_type": "income",
        "category": "Salary",
        "description": "Monthly salary",
        "days_ago": 15,
    },
    # Expenses from past 30 days
    {
        "telegram_id": "123",
        "amount": Decimal("25.50"),
        "transaction_type": "expense",
        "category": "Food",
        "description": "Lunch",
        "days_ago": 1,
    },
    {
        "telegram_id": "123",
        "amount": Decimal("45.00"),
        "transaction_type": "expense",
        "category": "Food",
        "description": "Dinner",
        "days_ago": 2,
    },
    {
        "telegram_id": "123",
        "amount": Decimal("15.00"),
        "transaction_type": "expense",
        "category": "Food",
        "description": "Coffee",
        "days_ago": 3,
    },
    {
        "telegram_id": "123",
        "amount": Decimal("50.00"),
        "transaction_type": "expense",
        "category": "Transport",
        "description": "Taxi fare",
        "days_ago": 2,
    },
    {
        "telegram_id": "123",
        "amount": Decimal("120.00"),
        "transaction_type": "expense",
        "category": "Transport",
        "description": "Gas",
        "days_ago": 5,
    },
    {
        "telegram_id": "123",
        "amount": Decimal("25.00"),
        "transaction_type": "expense",
        "category": "Entertainment",
        "description": "Movie ticket",
        "days_ago": 4,
    },
    {
        "telegram_id": "123",
        "amount": Decimal("80.00"),
        "transaction_type": "expense",
        "category": "Shopping",
        "description": "Clothes",
        "days_ago": 6,
    },
    {
        "telegram_id": "123",
        "amount": Decimal("150.00"),
        "transaction_type": "expense",
        "category": "Bills",
        "description": "Electricity",
        "days_ago": 7,
    },
    {
        "telegram_id": "123",
        "amount": Decimal("100.00"),
        "transaction_type": "expense",
        "category": "Bills",
        "description": "Internet",
        "days_ago": 8,
    },
    {
        "telegram_id": "123",
        "amount": Decimal("40.00"),
        "transaction_type": "expense",
        "category": "Health",
        "description": "Pharmacy",
        "days_ago": 10,
    },
    {
        "telegram_id": "123",
        "amount": Decimal("30.00"),
        "transaction_type": "expense",
        "category": "Food",
        "description": "Grocery",
        "days_ago": 12,
    },
    {
        "telegram_id": "123",
        "amount": Decimal("60.00"),
        "transaction_type": "expense",
        "category": "Shopping",
        "description": "Books",
        "days_ago": 14,
    },
]

for data in test_data:
    days_ago = data.pop("days_ago")
    cat_name = data.pop("category")
    description = data.pop("description")

    transaction_date = date.today() - timedelta(days=days_ago)

    transaction = Transaction.objects.create(
        telegram_id=data["telegram_id"],
        amount=data["amount"],
        transaction_type=data["transaction_type"],
        category_name=cat_name,
        category=categories[cat_name],
        note=description,
        transaction_date=transaction_date,
        is_recurring=False,
        tags="",
    )
    print(f"Created: {transaction.transaction_type.upper()} - {cat_name}: ${transaction.amount}")

print(
    f"\n✅ Test data populated! Total transactions: {Transaction.objects.filter(telegram_id='123').count()}"
)
