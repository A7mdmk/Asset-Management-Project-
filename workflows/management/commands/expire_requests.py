
from django.core.management.base import BaseCommand
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from workflows.models import Notification, ResourceRequest
from workflows.notification_services import create_notification


class Command(BaseCommand):
    help = "Expire pending resource requests past their deadline."

    def handle(self, *args, **options):
        now = timezone.now()
        expired_count = 0

        with transaction.atomic():
            requests = (
                ResourceRequest.objects
                .select_for_update()
                .select_related("asset", "requester")
                .filter(
                    status=ResourceRequest.Status.PENDING,
                    expires_at__lte=now,
                )
                .order_by("pk")
            )

            for resource_request in requests:
                resource_request.status = (
                    ResourceRequest.Status.EXPIRED
                )
                resource_request.save(
                    update_fields=["status", "updated_at"]
                )

                if resource_request.requester.is_active:
                    create_notification(
                        recipient=resource_request.requester,
                        notification_type=(
                            Notification.NotificationType.REQUEST
                        ),
                        title="Resource Request Expired",
                        message=(
                            f"Your request #{resource_request.pk} "
                            f"for {resource_request.asset.name} "
                            "has expired because it was not fully "
                            "approved within 48 hours."
                        ),
                        target_url=reverse("my_requests"),
                    )

                expired_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Expired {expired_count} pending request(s)."
            )
        )
