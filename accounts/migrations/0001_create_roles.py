
from django.db import migrations


def create_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")

    roles = [
        "Requester",
        "Custodian",
        "Approver/Admin",
    ]

    for role in roles:
        Group.objects.using(schema_editor.connection.alias).get_or_create(
            name=role
        )


def remove_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.using(schema_editor.connection.alias).filter(
        name__in=["Requester", "Custodian", "Approver/Admin"]
    ).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_roles, remove_roles),
    ]
