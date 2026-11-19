
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
