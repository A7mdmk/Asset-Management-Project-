
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class OperationalReportsTests(TestCase):

    def setUp(self):
        self.url = reverse("operational_reports")

        self.requester = User.objects.create_user(
            username="reports_requester",
            password="TestPassword123!",
        )

        self.custodian = User.objects.create_user(
            username="reports_custodian",
            password="TestPassword123!",
        )

        self.approver = User.objects.create_user(
            username="reports_approver",
            password="TestPassword123!",
        )

        self.staff = User.objects.create_user(
            username="reports_staff",
            password="TestPassword123!",
            is_staff=True,
        )

        self.admin = User.objects.create_superuser(
            username="reports_admin",
            email="reports@example.com",
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

    def test_requester_denied(self):
        self.client.force_login(self.requester)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_custodian_allowed(self):
        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_approver_allowed(self):
        self.client.force_login(self.approver)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_staff_allowed(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_superuser_allowed(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    @patch("assets.views.get_operational_report")
    def test_report_displays_data(self, mock_report):
        mock_report.return_value = {
            "total_assets": 4,
            "total_requests": 2,
            "pending_requests": 1,
            "approved_requests": 1,
            "rejected_requests": 0,
            "expired_requests": 0,
            "cancelled_requests": 0,
            "total_transfers": 1,
            "completed_transfers": 1,
            "transferred_units": 2,
            "total_maintenance": 0,
            "completed_maintenance": 0,
            "completed_dispositions": 0,
            "sustainability": {
                "available_units": 3,
                "reused_units": 2,
                "repaired_units": 0,
                "donated_units": 0,
                "recycled_units": 0,
            },
        }

        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operational Reports")
        self.assertContains(response, "Completed Transfers")

        self.assertEqual(
            response.context["report"]["total_assets"],
            4,
        )

        mock_report.assert_called_once_with()

    def test_empty_database_report(self):
        from assets.reporting_services import (
            get_operational_report,
        )

        report = get_operational_report()

        self.assertEqual(report["total_assets"], 0)
        self.assertEqual(report["total_requests"], 0)
        self.assertEqual(report["total_transfers"], 0)
        self.assertEqual(report["completed_maintenance"], 0)
        self.assertEqual(report["sustainability"]["reused_units"], 0)
