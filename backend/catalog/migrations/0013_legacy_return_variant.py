from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0012_restocknotification")]

    operations = [
        migrations.AddField(
            model_name="productvariant",
            name="is_legacy_return",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddConstraint(
            model_name="productvariant",
            constraint=models.UniqueConstraint(
                fields=("product",),
                condition=models.Q(is_legacy_return=True),
                name="one_legacy_return_variant",
            ),
        ),
    ]
