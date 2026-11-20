
import json

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from assets.models import Asset, Category, Department
from assets.services import register_asset
from .ai_recommendations import (
    get_available_assets,
    recommend_assets,
)


class AIRecommendationTests(TestCase):

    def setUp(self):
        self.department = Department.objects.create(
            name="Computer Science",
            code="CS-AI",
        )

        self.category = Category.objects.create(
            name="IT Equipment",
        )

        self.custodian = get_user_model().objects.create_user(
            username="ai_test_custodian",
            password="TestPassword123!",
        )

        self.asset = register_asset(
            name="Dell Monitor",
            description="24-inch computer monitor",
            category=self.category,
            department=self.department,
            custodian=self.custodian,
            location="CS Lab",
            tracking_mode=Asset.TrackingMode.INDIVIDUAL,
            quantity=1,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.PUBLISHED,
        )

    def test_available_assets_returns_published_asset(self):
        assets = get_available_assets()

        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["name"], "Dell Monitor")
        self.assertEqual(assets[0]["available_quantity"], 1)

    def test_draft_assets_are_excluded(self):
        self.asset.publication = Asset.Publication.DRAFT
        self.asset.save(update_fields=["publication"])

        self.assertEqual(get_available_assets(), [])

    def test_unsafe_assets_are_excluded(self):
        self.asset.condition = Asset.Condition.UNSAFE
        self.asset.save(update_fields=["condition"])

        self.assertEqual(get_available_assets(), [])

    def test_assets_without_free_stock_are_excluded(self):
        stock = self.asset.stock
        stock.free = 0
        stock.held = 1
        stock.full_clean()
        stock.save()

        self.assertEqual(get_available_assets(), [])

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_gemini_recommends_existing_asset(self, mock_client):
        mock_response = MagicMock()
        mock_response.text = json.dumps([str(self.asset.pk)])

        mock_client.return_value.models.generate_content.return_value = (
            mock_response
        )

        result = recommend_assets(
            "I need a computer monitor"
        )

        self.assertEqual(len(result["recommendations"]), 1)
        self.assertEqual(
            result["recommendations"][0]["id"],
            str(self.asset.pk),
        )
        self.assertEqual(
            result["recommendations"][0]["name"],
            "Dell Monitor",
        )

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_gemini_cannot_invent_asset_ids(self, mock_client):
        mock_response = MagicMock()
        mock_response.text = json.dumps(["fake-asset-id"])

        mock_client.return_value.models.generate_content.return_value = (
            mock_response
        )

        result = recommend_assets(
            "I need a laptop"
        )

        self.assertEqual(result["recommendations"], [])

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_empty_inventory_does_not_call_gemini(self, mock_client):
        self.asset.publication = Asset.Publication.DRAFT
        self.asset.save(update_fields=["publication"])

        result = recommend_assets(
            "I need a monitor"
        )

        self.assertEqual(result["recommendations"], [])
        mock_client.assert_not_called()

    def test_empty_user_request_is_rejected(self):
        with self.assertRaises(ValueError):
            recommend_assets("   ")

    # ==========================================================
    # AI RECOMMENDATION RELIABILITY EVALUATION
    # ==========================================================

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_ai_removes_duplicate_recommendations(self, mock_client):
        asset_id = str(self.asset.pk)

        mock_client.return_value.models.generate_content.return_value.text = (
            json.dumps([asset_id, asset_id, asset_id])
        )

        result = recommend_assets("I need a monitor")

        self.assertEqual(len(result["recommendations"]), 1)
        self.assertEqual(
            result["recommendations"][0]["id"],
            asset_id,
        )

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_ai_ignores_invented_ids(self, mock_client):
        asset_id = str(self.asset.pk)

        mock_client.return_value.models.generate_content.return_value.text = (
            json.dumps(["nonexistent-id", asset_id])
        )

        result = recommend_assets("Monitor for programming")

        self.assertEqual(len(result["recommendations"]), 1)
        self.assertEqual(
            result["recommendations"][0]["id"],
            asset_id,
        )

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_ai_rejects_invalid_json(self, mock_client):
        mock_client.return_value.models.generate_content.return_value.text = (
            "This is not JSON"
        )

        with self.assertRaises(ValueError):
            recommend_assets("I need a computer monitor")

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_ai_rejects_non_list_response(self, mock_client):
        mock_client.return_value.models.generate_content.return_value.text = (
            json.dumps({"asset": str(self.asset.pk)})
        )

        with self.assertRaises(ValueError):
            recommend_assets("I need a monitor")

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_ai_ignores_non_string_ids(self, mock_client):
        asset_id = str(self.asset.pk)

        mock_client.return_value.models.generate_content.return_value.text = (
            json.dumps([123, None, asset_id])
        )

        result = recommend_assets("Monitor")

        self.assertEqual(len(result["recommendations"]), 1)
        self.assertEqual(
            result["recommendations"][0]["id"],
            asset_id,
        )

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_ai_service_failure_does_not_change_stock(self, mock_client):
        mock_client.return_value.models.generate_content.side_effect = (
            RuntimeError("Gemini API unavailable")
        )

        with self.assertRaises(RuntimeError):
            recommend_assets("I need a monitor")

        self.asset.stock.refresh_from_db()

        self.assertEqual(self.asset.stock.free, 1)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.in_transit, 0)
        self.assertEqual(self.asset.stock.total, 1)

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_ai_recommendation_does_not_reserve_stock(self, mock_client):
        mock_client.return_value.models.generate_content.return_value.text = (
            json.dumps([str(self.asset.pk)])
        )

        recommend_assets("I need a monitor")

        self.asset.stock.refresh_from_db()

        self.assertEqual(self.asset.stock.free, 1)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.in_use, 0)
        self.assertEqual(self.asset.stock.total, 1)

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_ai_preserves_ranking_and_limits_results(self, mock_client):
        # Build four eligible assets for ranking evaluation.
        extra_assets = []

        for index in range(3):
            asset = register_asset(
                name=f"Test Monitor {index}",
                description="Monitor for computer lab work",
                category=self.category,
                department=self.department,
                custodian=self.custodian,
                location="CS Lab",
                tracking_mode=Asset.TrackingMode.INDIVIDUAL,
                quantity=1,
                condition=Asset.Condition.GOOD,
                lifecycle=Asset.Lifecycle.ACTIVE,
                publication=Asset.Publication.PUBLISHED,
            )
            extra_assets.append(asset)

        ranked_ids = [
            str(extra_assets[2].pk),
            str(self.asset.pk),
            str(extra_assets[0].pk),
            str(extra_assets[1].pk),
        ]

        mock_client.return_value.models.generate_content.return_value.text = (
            json.dumps(ranked_ids)
        )

        result = recommend_assets(
            "I need a monitor for programming"
        )

        returned_ids = [
            item["id"]
            for item in result["recommendations"]
        ]

        # Only the first three valid rankings are returned.
        self.assertEqual(returned_ids, ranked_ids[:3])
        self.assertEqual(len(returned_ids), 3)

        # Recommendations must not reserve stock.
        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 1)
        self.assertEqual(self.asset.stock.held, 0)

    # ==========================================================
    # AI RECOMMENDATION EXPLANATION TESTS
    # ==========================================================

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_ai_returns_explanation_with_recommendation(
        self, mock_client
    ):
        mock_client.return_value.models.generate_content.return_value.text = (
            json.dumps([{
                "id": str(self.asset.pk),
                "explanation": (
                    "The 24-inch monitor supports computer lab work."
                ),
            }])
        )

        result = recommend_assets("I need a monitor")

        self.assertEqual(len(result["recommendations"]), 1)
        self.assertEqual(
            result["recommendations"][0]["explanation"],
            "The 24-inch monitor supports computer lab work.",
        )

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_ai_supports_previous_id_only_format(self, mock_client):
        mock_client.return_value.models.generate_content.return_value.text = (
            json.dumps([str(self.asset.pk)])
        )

        result = recommend_assets("I need a monitor")

        self.assertEqual(len(result["recommendations"]), 1)
        self.assertIn(
            "explanation",
            result["recommendations"][0],
        )
        self.assertTrue(
            result["recommendations"][0]["explanation"]
        )

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_ai_handles_empty_explanation(self, mock_client):
        mock_client.return_value.models.generate_content.return_value.text = (
            json.dumps([{
                "id": str(self.asset.pk),
                "explanation": "   ",
            }])
        )

        result = recommend_assets("Monitor")

        self.assertEqual(
            result["recommendations"][0]["explanation"],
            "Recommended based on the available asset information.",
        )

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_ai_trims_explanation_whitespace(self, mock_client):
        mock_client.return_value.models.generate_content.return_value.text = (
            json.dumps([{
                "id": str(self.asset.pk),
                "explanation": "  Suitable for programming  ",
            }])
        )

        result = recommend_assets("Programming monitor")

        self.assertEqual(
            result["recommendations"][0]["explanation"],
            "Suitable for programming",
        )

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_ai_limits_explanation_length(self, mock_client):
        mock_client.return_value.models.generate_content.return_value.text = (
            json.dumps([{
                "id": str(self.asset.pk),
                "explanation": "A" * 1000,
            }])
        )

        result = recommend_assets("Monitor")

        self.assertEqual(
            len(result["recommendations"][0]["explanation"]),
            500,
        )

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_ai_rejects_invented_asset_with_explanation(
        self, mock_client
    ):
        mock_client.return_value.models.generate_content.return_value.text = (
            json.dumps([
                {
                    "id": "INVENTED-999",
                    "explanation": "A fictional computer",
                },
                {
                    "id": str(self.asset.pk),
                    "explanation": "Available monitor for lab work",
                },
            ])
        )

        result = recommend_assets("Computer equipment")

        self.assertEqual(len(result["recommendations"]), 1)
        self.assertEqual(
            result["recommendations"][0]["id"],
            str(self.asset.pk),
        )

    @patch("workflows.ai_recommendations.get_gemini_client")
    def test_ai_prompt_requires_grounded_explanations(
        self, mock_client
    ):
        mock_client.return_value.models.generate_content.return_value.text = (
            json.dumps([])
        )

        recommend_assets("I need a monitor")

        call = (
            mock_client.return_value.models.generate_content
            .call_args
        )

        prompt = call.kwargs["contents"]

        self.assertIn(
            'Each object must contain "id" and "explanation"',
            prompt,
        )
        self.assertIn(
            "Do not invent specifications or features",
            prompt,
        )
