from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0009_chatmessage_media_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChatMessageRevision",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("telegram_id", models.BigIntegerField()),
                ("old_message", models.TextField()),
                ("new_message", models.TextField()),
                ("action", models.CharField(default="edit", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "chat_message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="revisions",
                        to="tracker.chatmessage",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="chatmessagerevision",
            index=models.Index(fields=["telegram_id", "created_at"], name="chatrev_tel_created_idx"),
        ),
        migrations.AddIndex(
            model_name="chatmessagerevision",
            index=models.Index(fields=["chat_message", "created_at"], name="chatrev_msg_created_idx"),
        ),
    ]
