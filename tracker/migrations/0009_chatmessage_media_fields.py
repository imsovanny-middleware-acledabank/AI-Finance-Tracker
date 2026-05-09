from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0008_transaction_transaction_amount_gt_zero"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatmessage",
            name="image_base64",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="image_mime",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="audio_base64",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="audio_mime",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
