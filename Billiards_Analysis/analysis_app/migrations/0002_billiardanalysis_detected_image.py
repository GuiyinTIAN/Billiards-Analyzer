# Generated by Django 4.2.20 on 2025-04-22 15:16

import analysis_app.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analysis_app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="billiardanalysis",
            name="detected_image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=analysis_app.models.image_upload_path,
                verbose_name="检测结果图片",
            ),
        ),
    ]
