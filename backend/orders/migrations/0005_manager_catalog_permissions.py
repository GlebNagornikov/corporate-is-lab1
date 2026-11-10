from django.db import migrations


def grant_catalog_permissions(apps, schema_editor):
    database = schema_editor.connection.alias
    group = (
        apps.get_model("auth", "Group")
        .objects.using(database)
        .filter(name="Менеджеры магазина")
        .first()
    )
    if group is None:
        return
    permissions = (
        apps.get_model("auth", "Permission")
        .objects.using(database)
        .filter(
            content_type__app_label="catalog",
            codename__in=["add_category", "delete_product"],
        )
    )
    group.permissions.add(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0010_bookedition"),
        ("orders", "0004_emailnotification"),
    ]
    operations = [migrations.RunPython(grant_catalog_permissions, migrations.RunPython.noop)]
