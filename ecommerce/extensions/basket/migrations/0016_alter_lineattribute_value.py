# Generated by Django 3.2.20 on 2023-12-05 10:34

import django.core.serializers.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('basket', '0015_add_paymentintentid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lineattribute',
            name='value',
            field=models.JSONField(encoder=django.core.serializers.json.DjangoJSONEncoder, verbose_name='Value'),
        ),
    ]