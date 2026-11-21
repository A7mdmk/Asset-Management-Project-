
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from workflows.models import Notification


User = get_user_model()


class NotificationsViewTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="inbox_user",
            password="TestPassword123!",
        )

        self.other_user = User.objects.create_user(
            username="inbox_other",
            password="TestPassword123!",
        )

        self.url = reverse("notifications")

    def make_notification(
        self,
        recipient=None,
        title="Test Notification",
        is_read=False,
    ):
        return Notification.objects.create(
            recipient=recipient or self.user,
            notification_type=(
                Notification.NotificationType.REQUEST
            ),
            title=title,
            message="This is a test notification.",
            is_read=is_read,
        )

    def test_anonymous_user_redirected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_authenticated_user_can_open_inbox(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "workflows/notifications.html",
        )

    def test_empty_inbox_message(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertContains(
            response,
            "No notifications yet.",
        )

    def test_user_sees_own_notifications(self):
        self.make_notification(title="My Request Update")

        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertContains(
            response,
            "My Request Update",
        )

    def test_other_user_notifications_hidden(self):
        self.make_notification(
            recipient=self.other_user,
            title="Private Notification",
        )

        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertNotContains(
            response,
            "Private Notification",
        )

    def test_unread_count_correct(self):
        self.make_notification(
            title="Unread One",
        )
        self.make_notification(
            title="Unread Two",
        )
        self.make_notification(
            title="Read One",
            is_read=True,
        )

        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(
            response.context["unread_count"],
            2,
        )

    def test_read_and_unread_labels_displayed(self):
        self.make_notification(
            title="Already Read",
            is_read=True,
        )
        self.make_notification(
            title="Still Unread",
        )

        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertContains(response, "Already Read")
        self.assertContains(response, "Still Unread")
        self.assertContains(response, "Unread")

    def test_pagination_limits_to_ten(self):
        for index in range(12):
            self.make_notification(
                title=f"Notification {index}",
            )

        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(response.context["notifications"]),
            10,
        )

        self.assertTrue(
            response.context["page_obj"].has_next()
        )

    def test_second_page_contains_remaining(self):
        for index in range(12):
            self.make_notification(
                title=f"Notification {index}",
            )

        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {"page": 2},
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            len(response.context["notifications"]),
            2,
        )

    def test_dashboard_shows_unread_count(self):
        self.make_notification(
            title="Unread Notification",
        )
        self.make_notification(
            title="Read Notification",
            is_read=True,
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse("dashboard")
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["unread_notifications"],
            1,
        )

        self.assertContains(
            response,
            "View Notifications",
        )
