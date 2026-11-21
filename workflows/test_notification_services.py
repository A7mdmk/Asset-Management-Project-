
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.test import TestCase

from workflows.models import Notification
from workflows.notification_services import (
    create_notification,
    mark_notification_read,
)


User = get_user_model()


class NotificationServiceTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="notification_user",
            password="TestPassword123!",
        )

        self.other_user = User.objects.create_user(
            username="notification_other",
            password="TestPassword123!",
        )

        self.valid_data = {
            "recipient": self.user,
            "notification_type": (
                Notification.NotificationType.REQUEST
            ),
            "title": "Request Submitted",
            "message": "Your asset request was submitted.",
            "target_url": "/workflows/requests/",
        }

    def test_create_notification_success(self):
        notification = create_notification(
            **self.valid_data
        )

        self.assertEqual(
            notification.recipient,
            self.user,
        )

        self.assertEqual(
            notification.title,
            "Request Submitted",
        )

        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)

        self.assertEqual(
            Notification.objects.count(),
            1,
        )

    def test_create_notification_strips_whitespace(self):
        data = self.valid_data.copy()

        data["title"] = "  Request Submitted  "
        data["message"] = "  Your request was submitted.  "

        notification = create_notification(**data)

        self.assertEqual(
            notification.title,
            "Request Submitted",
        )

        self.assertEqual(
            notification.message,
            "Your request was submitted.",
        )

    def test_inactive_recipient_rejected(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            create_notification(**self.valid_data)

        self.assertEqual(
            Notification.objects.count(),
            0,
        )

    def test_invalid_notification_type_rejected(self):
        data = self.valid_data.copy()
        data["notification_type"] = "InvalidType"

        with self.assertRaises(ValidationError):
            create_notification(**data)

        self.assertFalse(
            Notification.objects.exists()
        )

    def test_empty_title_rejected(self):
        data = self.valid_data.copy()
        data["title"] = "   "

        with self.assertRaises(ValidationError):
            create_notification(**data)

        self.assertFalse(
            Notification.objects.exists()
        )

    def test_external_redirect_url_rejected(self):
        data = self.valid_data.copy()
        data["target_url"] = "https://example.com"

        with self.assertRaises(ValidationError):
            create_notification(**data)

        self.assertFalse(
            Notification.objects.exists()
        )

    def test_mark_notification_read_success(self):
        notification = create_notification(
            **self.valid_data
        )

        result = mark_notification_read(
            actor=self.user,
            notification_id=notification.pk,
        )

        self.assertTrue(result.is_read)
        self.assertIsNotNone(result.read_at)

        notification.refresh_from_db()

        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_mark_read_is_idempotent(self):
        notification = create_notification(
            **self.valid_data
        )

        first = mark_notification_read(
            actor=self.user,
            notification_id=notification.pk,
        )

        original_read_at = first.read_at

        second = mark_notification_read(
            actor=self.user,
            notification_id=notification.pk,
        )

        self.assertEqual(
            second.read_at,
            original_read_at,
        )

    def test_other_user_cannot_mark_notification_read(self):
        notification = create_notification(
            **self.valid_data
        )

        with self.assertRaises(ValidationError):
            mark_notification_read(
                actor=self.other_user,
                notification_id=notification.pk,
            )

        notification.refresh_from_db()

        self.assertFalse(notification.is_read)

    def test_anonymous_user_cannot_mark_read(self):
        notification = create_notification(
            **self.valid_data
        )

        with self.assertRaises(ValidationError):
            mark_notification_read(
                actor=AnonymousUser(),
                notification_id=notification.pk,
            )

        notification.refresh_from_db()

        self.assertFalse(notification.is_read)
