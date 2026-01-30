"""Add phone_number field to UserProfile.

Generated manually to match the current `UserProfile` model which includes
`phone_number` but lacks a corresponding migration. This adds a nullable,
blankable CharField so it can be applied safely to existing databases.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zaoapp", "0010_paymentanalytics"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="phone_number",
            field=models.CharField(max_length=20, null=True, blank=True, help_text="M-Pesa phone number"),
        ),
    ]
