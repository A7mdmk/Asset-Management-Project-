
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from workflows.models import ResourceRequest


class Command(BaseCommand):
    help = "Expire pending resource requests past their deadline."

    def handle(self, *args, **options):
        now = timezone.now()
        expired_count = 0

        with transaction.atomic():
            expired_count = ResourceRequest.objects.filter(
                status=ResourceRequest.Status.PENDING,
                expires_at__lte=now,
            ).update(
                status=ResourceRequest.Status.EXPIRED,
                updated_at=now,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Expired {expired_count} pending request(s)."
            )
        )
