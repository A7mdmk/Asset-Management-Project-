
import csv
import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class ReportCSVExportTests(TestCase):

    def setUp(self):
        self.url = reverse("export_reports_csv")

        self.requester = User.objects.create_user(
            username="csv_requester",
            password="TestPassword123!",
        )

        self.custodian = User.objects.create_user(
            username="csv_custodian",
            password="TestPassword123!",
        )

        self.approver = User.objects.create_user(
            username="csv_approver",
            password="TestPassword123!",
        )

        self.staff = User.objects.create_user(
            username="csv_staff",
            password="TestPassword123!",
            is_staff=True,
        )

        self.admin = User.objects.create_superuser(
            username="csv_admin",
            email="csv_admin@example.com",
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

    def read_csv(self, response):
        content = response.content.decode("utf-8-sig")
        return list(csv.reader(io.StringIO(content)))

    def test_anonymous_user_redirected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_requester_denied(self):
        self.client.force_login(self.requester)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_custodian_can_export(self):
        self.client.force_login(self.custodian)

        response = self.client.get(
            self.url,
            {"type": "operational"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "text/csv",
            response["Content-Type"],
        )

    def test_approver_can_export(self):
        self.client.force_login(self.approver)

        response = self.client.get(
            self.url,
            {"type": "sustainability"},
        )

        self.assertEqual(response.status_code, 200)

    def test_staff_and_admin_can_export(self):
        for user in [self.staff, self.admin]:
            with self.subTest(username=user.username):
                self.client.force_login(user)

                response = self.client.get(self.url)

                self.assertEqual(response.status_code, 200)

    def test_invalid_report_type_rejected(self):
        self.client.force_login(self.custodian)

        response = self.client.get(
            self.url,
            {"type": "invalid"},
        )

        self.assertEqual(response.status_code, 400)

    @patch("assets.views.get_operational_report")
    def test_operational_csv_content(self, mock_report):
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
        }

        self.client.force_login(self.custodian)

        response = self.client.get(
            self.url,
            {"type": "operational"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "operational_report.csv",
            response["Content-Disposition"],
        )

        rows = self.read_csv(response)

        self.assertEqual(rows[0], ["Metric", "Value"])
        self.assertIn(["Total Assets", "4"], rows)
        self.assertIn(["Total Requests", "2"], rows)
        self.assertIn(["Transferred Units", "2"], rows)

        mock_report.assert_called_once_with()

    @patch("assets.views.get_sustainability_summary")
    def test_sustainability_csv_content(self, mock_summary):
        mock_summary.return_value = {
            "total_registered_assets": 4,
            "available_units": 3,
            "reused_units": 2,
            "repaired_units": 1,
            "donated_units": 0,
            "recycled_units": 0,
        }

        self.client.force_login(self.custodian)

        response = self.client.get(
            self.url,
            {"type": "sustainability"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "sustainability_report.csv",
            response["Content-Disposition"],
        )

        rows = self.read_csv(response)

        self.assertEqual(rows[0], ["Metric", "Value"])
        self.assertIn(["Registered Asset Records", "4"], rows)
        self.assertIn(["Available Units", "3"], rows)
        self.assertIn(["Reused Units", "2"], rows)

        mock_summary.assert_called_once_with()
