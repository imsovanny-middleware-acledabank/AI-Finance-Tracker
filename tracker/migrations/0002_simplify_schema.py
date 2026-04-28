# Generated migration - simplify schema for better compatibility

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0001_initial"),
    ]

    operations = [
        # First, rename the old category field to category_name
        migrations.RenameField(
            model_name="transaction",
            old_name="category",
            new_name="category_name",
        ),
        # Add the new category ForeignKey (nullable initially)
        migrations.CreateModel(
            name="Category",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=50, unique=True)),
                ("icon", models.CharField(default="💰", max_length=10)),
                ("description", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name_plural": "Categories",
            },
        ),
        migrations.CreateModel(
            name="Budget",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("telegram_id", models.BigIntegerField()),
                ("limit_amount", models.DecimalField(decimal_places=2, max_digits=15)),
                (
                    "frequency",
                    models.CharField(
                        choices=[
                            ("daily", "Daily"),
                            ("weekly", "Weekly"),
                            ("monthly", "Monthly"),
                            ("yearly", "Yearly"),
                        ],
                        default="monthly",
                        max_length=10,
                    ),
                ),
                (
                    "alert_threshold",
                    models.IntegerField(default=80, help_text="Alert when % of budget is spent"),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="tracker.category"
                    ),
                ),
            ],
            options={
                "ordering": ["category__name"],
                "unique_together": {("telegram_id", "category", "frequency")},
            },
        ),
        # Add new fields to Transaction (nullable first)
        migrations.AddField(
            model_name="transaction",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="tracker.category",
            ),
        ),
        migrations.AddField(
            model_name="transaction",
            name="tags",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="transaction",
            name="is_recurring",
            field=models.BooleanField(default=False),
        ),
        # Add indexes for performance
        migrations.AddIndex(
            model_name="transaction",
            index=models.Index(
                fields=["telegram_id", "-transaction_date"], name="tracker_tran_telegramid_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="transaction",
            index=models.Index(
                fields=["telegram_id", "transaction_type"], name="tracker_tran_type_idx"
            ),
        ),
    ]
