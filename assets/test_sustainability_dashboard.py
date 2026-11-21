
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from assets.sustainability_services import (
    get_sustainability_summary,
)


User = get_user_model()


class SustainabilityDashboardTests(TestCase):

    def setUp(self):
        self.url = reverse("sustainability_dashboard")

        self.requester = User.objects.create_user(
            username="sustainability_requester",
            password="TestPassword123!",
        )

        self.custodian = User.objects.create_user(
            username="sustainability_custodian",
            password="TestPassword123!",
        )

        self.approver = User.objects.create_user(
            username="sustainability_approver",
            password="TestPassword123!",
        )

        self.staff_user = User.objects.create_user(
            username="sustainability_staff",
            password="TestPassword123!",
            is_staff=True,
        )

        self.admin = User.objects.create_superuser(
            username="sustainability_admin",
            email="admin@example.com",
            password="TestPassword123!",
        )

        custodian_group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        approver_group, _ = Group.objects.get_or_create(
            name="Approver/Admin"
        )

        self.custodian.groups.add(custodian_group)
        self.approver.groups.add(approver_group)

    def test_anonymous_user_redirected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_requester_cannot_access_dashboard(self):
        self.client.force_login(self.requester)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_custodian_can_access_dashboard(self):
        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_approver_can_access_dashboard(self):
        self.client.force_login(self.approver)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_staff_can_access_dashboard(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_superuser_can_access_dashboard(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    @patch(
        "assets.views.get_sustainability_summary"
    )
    def test_dashboard_displays_summary(self, mock_summary):
        mock_summary.return_value = {
            "total_registered_assets": 10,
            "available_units": 20,
            "reused_units": 5,
            "repaired_units": 3,
            "donated_units": 2,
            "recycled_units": 1,
        }

        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["summary"]["reused_units"],
            5,
        )

        self.assertContains(
            response,
            "Sustainability Dashboard",
        )

        mock_summary.assert_called_once_with()

    def test_empty_database_returns_zero_metrics(self):
        summary = get_sustainability_summary()

        self.assertEqual(
            summary["total_registered_assets"],
            0,
        )

        self.assertEqual(
            summary["available_units"],
            0,
        )

        self.assertEqual(
            summary["reused_units"],
            0,
        )

        self.assertEqual(
            summary["repaired_units"],
            0,
        )

        self.assertEqual(
            summary["donated_units"],
            0,
        )

        self.assertEqual(
            summary["recycled_units"],
            0,
        )
