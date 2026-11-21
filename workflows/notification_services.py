
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Notification


@transaction.atomic
def create_notification(
    *,
    recipient,
    notification_type,
    title,
    message,
    target_url="",
):
    """
    Create a notification for an active user.
    """

    if (
        recipient is None
        or not recipient.is_authenticated
        or not recipient.is_active
    ):
        raise ValidationError(
            "An active recipient is required."
        )

    valid_types = {
        choice.value
        for choice in Notification.NotificationType
    }

    if notification_type not in valid_types:
        raise ValidationError(
            "Invalid notification type."
        )

    title = (title or "").strip()
    message = (message or "").strip()
    target_url = (target_url or "").strip()

    if not title:
        raise ValidationError(
            "Notification title is required."
        )

    if len(title) > 150:
        raise ValidationError(
            "Notification title cannot exceed 150 characters."
        )

    if not message:
        raise ValidationError(
            "Notification message is required."
        )

    if len(message) > 1000:
        raise ValidationError(
            "Notification message cannot exceed 1000 characters."
        )

    if len(target_url) > 500:
        raise ValidationError(
            "Notification target URL cannot exceed 500 characters."
        )

    if target_url and (
        not target_url.startswith("/")
        or target_url.startswith("//")
        or "\\" in target_url
        or any(ord(char) < 32 for char in target_url)
    ):
        raise ValidationError(
            "Notification target URL must be a local application path."
        )

    notification = Notification(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        target_url=target_url,
    )

    notification.full_clean()
    notification.save()

    return notification


@transaction.atomic
def mark_notification_read(*, actor, notification_id):
    """
    Mark a notification as read.

    Users may only mark their own notifications as read.
    Repeating the action is safe.
    """

    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
    ):
        raise ValidationError(
            "An active account is required."
        )

    notification = (
        Notification.objects
        .select_for_update()
        .filter(
            pk=notification_id,
            recipient=actor,
        )
        .first()
    )

    if notification is None:
        raise ValidationError(
            "Notification not found or access denied."
        )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()

        notification.save(
            update_fields=[
                "is_read",
                "read_at",
            ]
        )

    return notification
