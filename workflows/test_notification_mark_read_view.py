
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from workflows.models import Notification


User = get_user_model()


class NotificationMarkReadViewTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="mark_read_user",
            password="TestPassword123!",
        )

        self.other_user = User.objects.create_user(
            username="mark_read_other",
            password="TestPassword123!",
        )

        self.notification = Notification.objects.create(
            recipient=self.user,
            notification_type=(
                Notification.NotificationType.REQUEST
            ),
            title="Request Update",
            message="Your request has been updated.",
        )

        self.url = reverse(
            "notification_mark_read",
            args=[self.notification.pk],
        )

    def test_anonymous_user_redirected(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)

        self.notification.refresh_from_db()
        self.assertFalse(self.notification.is_read)

    def test_get_request_not_allowed(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "POST")

        self.notification.refresh_from_db()
        self.assertFalse(self.notification.is_read)

    def test_put_request_not_allowed(self):
        self.client.force_login(self.user)

        response = self.client.put(self.url)

        self.assertEqual(response.status_code, 405)

    @patch("workflows.views.mark_notification_read")
    def test_valid_post_calls_service(self, service):
        self.client.force_login(self.user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)

        service.assert_called_once_with(
            actor=self.user,
            notification_id=self.notification.pk,
        )

    @patch("workflows.views.mark_notification_read")
    def test_success_redirects_to_inbox(self, service):
        self.client.force_login(self.user)

        response = self.client.post(self.url)

        self.assertRedirects(
            response,
            reverse("notifications"),
            fetch_redirect_response=False,
        )

    @patch("workflows.views.mark_notification_read")
    def test_success_message_displayed(self, service):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            follow=True,
        )

        self.assertContains(
            response,
            "Notification marked as read.",
        )

    def test_real_post_marks_notification_read(self):
        self.client.force_login(self.user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)

        self.notification.refresh_from_db()

        self.assertTrue(self.notification.is_read)
        self.assertIsNotNone(self.notification.read_at)

    def test_other_user_cannot_mark_read(self):
        self.client.force_login(self.other_user)

        response = self.client.post(
            self.url,
            follow=True,
        )

        self.assertEqual(response.status_code, 200)

        self.notification.refresh_from_db()
        self.assertFalse(self.notification.is_read)

        self.assertContains(
            response,
            "Notification not found or access denied.",
        )

    @patch("workflows.views.mark_notification_read")
    def test_service_validation_error_displayed(self, service):
        self.client.force_login(self.user)

        service.side_effect = ValidationError(
            "Notification could not be updated."
        )

        response = self.client.post(
            self.url,
            follow=True,
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Notification could not be updated.",
        )

    def test_read_notification_has_no_mark_read_button(self):
        self.notification.is_read = True
        self.notification.save(update_fields=["is_read"])

        self.client.force_login(self.user)

        response = self.client.get(
            reverse("notifications")
        )

        self.assertEqual(response.status_code, 200)

        self.assertNotContains(
            response,
            "Mark as Read",
        )
