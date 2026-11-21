
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class AIReportingViewTests(TestCase):

    def setUp(self):
        self.url = reverse("ai_operational_report")

        self.custodian = User.objects.create_user(
            username="ai_report_custodian",
            password="TestPassword123!",
        )

        self.requester = User.objects.create_user(
            username="ai_report_requester",
            password="TestPassword123!",
        )

        self.approver = User.objects.create_user(
            username="ai_report_approver",
            password="TestPassword123!",
        )

        custodian_group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        requester_group, _ = Group.objects.get_or_create(
            name="Requester"
        )

        approver_group, _ = Group.objects.get_or_create(
            name="Approver/Admin"
        )

        self.custodian.groups.add(custodian_group)
        self.requester.groups.add(requester_group)
        self.approver.groups.add(approver_group)

        self.mock_report = {
            "summary": "Recorded operations overview.",
            "observations": [
                "Transfers have been recorded.",
            ],
            "limitations": [
                "No historical comparison is available.",
            ],
            "verified_metrics": {
                "total_assets": 5,
                "total_requests": 3,
                "completed_transfers": 1,
                "transferred_units": 2,
                "completed_maintenance": 1,
                "completed_dispositions": 0,
            },
            "data_readiness": {},
            "requires_review": True,
        }

    def test_anonymous_user_redirected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_requester_access_denied(self):
        self.client.force_login(self.requester)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_custodian_can_open_page(self):
        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "AI-Generated Operational Report",
        )

    def test_approver_can_open_page(self):
        self.client.force_login(self.approver)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_get_does_not_call_gemini(self):
        self.client.force_login(self.custodian)

        with patch(
            "assets.views.generate_ai_operational_report"
        ) as mock_generate:
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        mock_generate.assert_not_called()

    @patch("assets.views.generate_ai_operational_report")
    def test_valid_post_generates_report(self, mock_generate):
        mock_generate.return_value = self.mock_report

        self.client.force_login(self.custodian)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Recorded operations overview.",
        )

        mock_generate.assert_called_once_with()

    @patch("assets.views.generate_ai_operational_report")
    def test_observations_are_displayed(self, mock_generate):
        mock_generate.return_value = self.mock_report

        self.client.force_login(self.custodian)

        response = self.client.post(self.url)

        self.assertContains(
            response,
            "Transfers have been recorded.",
        )

    @patch("assets.views.generate_ai_operational_report")
    def test_limitations_are_displayed(self, mock_generate):
        mock_generate.return_value = self.mock_report

        self.client.force_login(self.custodian)

        response = self.client.post(self.url)

        self.assertContains(
            response,
            "No historical comparison is available.",
        )

    @patch("assets.views.generate_ai_operational_report")
    def test_verified_metrics_are_displayed(
        self,
        mock_generate,
    ):
        mock_generate.return_value = self.mock_report

        self.client.force_login(self.custodian)

        response = self.client.post(self.url)

        self.assertContains(
            response,
            "Verified Operational Metrics",
        )

        self.assertContains(
            response,
            "Transferred Units",
        )

    @patch("assets.views.generate_ai_operational_report")
    def test_gemini_failure_is_handled(self, mock_generate):
        mock_generate.side_effect = ValueError(
            "Gemini unavailable."
        )

        self.client.force_login(self.custodian)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "AI reporting is temporarily unavailable.",
        )
