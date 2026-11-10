from django.db import migrations, models


def preserve_visibility(apps, schema_editor):
    reviews = apps.get_model("catalog", "Review").objects.using(schema_editor.connection.alias)
    reviews.filter(is_published=True).update(status="approved")
    reviews.filter(is_published=False).update(status="rejected")


def restore_visibility(apps, schema_editor):
    reviews = apps.get_model("catalog", "Review").objects.using(schema_editor.connection.alias)
    reviews.exclude(status="approved").update(is_published=False)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0010_bookedition")]

    operations = [
        migrations.AddField(
            model_name="review",
            name="status",
            field=models.CharField(
                "Состояние",
                max_length=8,
                choices=[
                    ("pending", "На модерации"),
                    ("approved", "Одобрен"),
                    ("rejected", "Отклонён"),
                ],
                default="pending",
                db_index=True,
            ),
        ),
        migrations.RunPython(preserve_visibility, restore_visibility),
        migrations.RemoveField(model_name="review", name="is_published"),
        migrations.AlterModelOptions(
            name="review",
            options={
                "ordering": ["-created_at", "-pk"],
                "verbose_name": "отзыв",
                "verbose_name_plural": "отзывы",
            },
        ),
    ]
