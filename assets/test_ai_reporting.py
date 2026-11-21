
import json
from unittest.mock import MagicMock, patch

from django.test import TestCase

from assets.ai_reporting import (
    generate_ai_operational_report,
)


class AIReportingTests(TestCase):

    def setUp(self):
        self.report = {
            "total_assets": 5,
            "total_requests": 3,
            "pending_requests": 1,
            "approved_requests": 2,
            "rejected_requests": 0,
            "expired_requests": 0,
            "cancelled_requests": 0,
            "total_transfers": 2,
            "completed_transfers": 1,
            "transferred_units": 2,
            "total_maintenance": 1,
            "completed_maintenance": 1,
            "completed_dispositions": 0,
            "sustainability": {
                "total_registered_assets": 5,
                "available_units": 3,
                "reused_units": 2,
                "repaired_units": 1,
                "donated_units": 0,
                "recycled_units": 0,
            },
        }

        self.readiness = {
            "total_assets": 5,
            "assets_with_value": 3,
            "assets_with_mass": 2,
            "assets_with_both": 2,
            "assets_missing_value": 2,
            "assets_missing_mass": 3,
        }

    def mock_response(self, data):
        client = MagicMock()
        client.models.generate_content.return_value.text = (
            json.dumps(data)
        )
        return client

    def run_report(self, response_data):
        with (
            patch(
                "assets.ai_reporting.get_operational_report",
                return_value=self.report,
            ),
            patch(
                "assets.ai_reporting.get_sustainability_data_readiness",
                return_value=self.readiness,
            ),
            patch(
                "assets.ai_reporting.get_gemini_client",
                return_value=self.mock_response(response_data),
            ),
        ):
            return generate_ai_operational_report()

    def test_valid_report(self):
        result = self.run_report({
            "summary": "The inventory has recorded activity.",
            "observations": [
                "Transfers have been recorded.",
                "Maintenance has been completed.",
            ],
            "limitations": [
                "No historical comparison is available.",
            ],
        })

        self.assertEqual(
            result["summary"],
            "The inventory has recorded activity.",
        )
        self.assertEqual(
            len(result["observations"]),
            2,
        )
        self.assertTrue(result["requires_review"])

    def test_verified_metrics_preserved(self):
        result = self.run_report({
            "summary": "Recorded operations overview.",
            "observations": [],
            "limitations": [],
        })

        self.assertEqual(
            result["verified_metrics"],
            self.report,
        )
        self.assertEqual(
            result["data_readiness"],
            self.readiness,
        )

    def test_missing_summary_rejected(self):
        with self.assertRaises(ValueError):
            self.run_report({
                "observations": [],
                "limitations": [],
            })

    def test_empty_summary_rejected(self):
        with self.assertRaises(ValueError):
            self.run_report({
                "summary": "   ",
                "observations": [],
                "limitations": [],
            })

    def test_non_object_response_rejected(self):
        with self.assertRaises(ValueError):
            self.run_report([
                {"summary": "Invalid structure"}
            ])

    def test_invalid_observations_rejected(self):
        with self.assertRaises(ValueError):
            self.run_report({
                "summary": "Valid summary.",
                "observations": "Not a list",
                "limitations": [],
            })

    def test_invalid_limitations_rejected(self):
        with self.assertRaises(ValueError):
            self.run_report({
                "summary": "Valid summary.",
                "observations": [],
                "limitations": "Not a list",
            })

    def test_long_summary_truncated(self):
        result = self.run_report({
            "summary": "A" * 1500,
            "observations": [],
            "limitations": [],
        })

        self.assertEqual(
            len(result["summary"]),
            1000,
        )

    def test_observations_limited_to_three(self):
        result = self.run_report({
            "summary": "Valid summary.",
            "observations": [
                "One", "Two", "Three", "Four",
            ],
            "limitations": [],
        })

        self.assertEqual(
            result["observations"],
            ["One", "Two", "Three"],
        )

    def test_invalid_list_items_ignored(self):
        result = self.run_report({
            "summary": "Valid summary.",
            "observations": [
                "", None, 123, "Valid observation",
            ],
            "limitations": [
                None, "Valid limitation",
            ],
        })

        self.assertEqual(
            result["observations"],
            ["Valid observation"],
        )
        self.assertEqual(
            result["limitations"],
            ["Valid limitation"],
        )

    def test_invalid_json_rejected(self):
        client = MagicMock()
        client.models.generate_content.return_value.text = (
            "not valid json"
        )

        with (
            patch(
                "assets.ai_reporting.get_operational_report",
                return_value=self.report,
            ),
            patch(
                "assets.ai_reporting.get_sustainability_data_readiness",
                return_value=self.readiness,
            ),
            patch(
                "assets.ai_reporting.get_gemini_client",
                return_value=client,
            ),
        ):
            with self.assertRaises(ValueError):
                generate_ai_operational_report()

    def test_report_does_not_create_assets(self):
        from assets.models import Asset

        initial_count = Asset.objects.count()

        self.run_report({
            "summary": "Recorded activity overview.",
            "observations": [],
            "limitations": [],
        })

        self.assertEqual(
            Asset.objects.count(),
            initial_count,
        )
