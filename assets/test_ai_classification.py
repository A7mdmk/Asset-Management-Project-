
import json
from unittest.mock import patch, MagicMock

from django.test import TestCase

from assets.models import Category
from workflows.ai_classification import (
    suggest_asset_category,
)


class AIClassificationTests(TestCase):

    def setUp(self):
        self.it_category = Category.objects.create(
            name="IT Equipment",
            description="Computers and electronic equipment",
        )

        self.furniture_category = Category.objects.create(
            name="Furniture",
            description="Office furniture and seating",
        )

    def mock_gemini(self, response_data):
        client = MagicMock()
        client.models.generate_content.return_value.text = (
            json.dumps(response_data)
        )
        return client

    @patch("workflows.ai_classification.get_gemini_client")
    def test_valid_category_suggestion(self, mock_client):
        mock_client.return_value = self.mock_gemini({
            "category_id": self.it_category.pk,
            "explanation": "This asset is a computer.",
        })

        result = suggest_asset_category(
            name="Dell Laptop",
            description="Laptop for programming.",
        )

        self.assertEqual(
            result["category_id"],
            self.it_category.pk,
        )
        self.assertEqual(
            result["category_name"],
            "IT Equipment",
        )
        self.assertTrue(result["requires_review"])

    @patch("workflows.ai_classification.get_gemini_client")
    def test_numeric_string_category_id(self, mock_client):
        mock_client.return_value = self.mock_gemini({
            "category_id": str(self.furniture_category.pk),
            "explanation": "This asset is furniture.",
        })

        result = suggest_asset_category(
            name="Office Chair",
        )

        self.assertEqual(
            result["category_id"],
            self.furniture_category.pk,
        )

    @patch("workflows.ai_classification.get_gemini_client")
    def test_invented_category_rejected(self, mock_client):
        mock_client.return_value = self.mock_gemini({
            "category_id": 999999,
            "explanation": "Invented category.",
        })

        with self.assertRaises(ValueError):
            suggest_asset_category(
                name="Dell Laptop",
            )

    @patch("workflows.ai_classification.get_gemini_client")
    def test_boolean_category_id_rejected(self, mock_client):
        mock_client.return_value = self.mock_gemini({
            "category_id": True,
            "explanation": "Invalid identifier.",
        })

        with self.assertRaises(ValueError):
            suggest_asset_category(
                name="Office Chair",
            )

    @patch("workflows.ai_classification.get_gemini_client")
    def test_no_matching_category(self, mock_client):
        mock_client.return_value = self.mock_gemini({
            "category_id": None,
            "explanation": "No suitable category exists.",
        })

        result = suggest_asset_category(
            name="Unknown Specialized Equipment",
        )

        self.assertIsNone(result["category_id"])
        self.assertIsNone(result["category_name"])
        self.assertTrue(result["requires_review"])

    @patch("workflows.ai_classification.get_gemini_client")
    def test_invalid_json_rejected(self, mock_client):
        client = MagicMock()
        client.models.generate_content.return_value.text = (
            "not valid json"
        )
        mock_client.return_value = client

        with self.assertRaises(ValueError):
            suggest_asset_category(
                name="Dell Laptop",
            )

    @patch("workflows.ai_classification.get_gemini_client")
    def test_invalid_response_structure(self, mock_client):
        mock_client.return_value = self.mock_gemini([
            {"category_id": self.it_category.pk}
        ])

        with self.assertRaises(ValueError):
            suggest_asset_category(
                name="Dell Laptop",
            )

    def test_empty_asset_name_rejected(self):
        with self.assertRaises(ValueError):
            suggest_asset_category(
                name="   ",
            )

    def test_invalid_description_rejected(self):
        with self.assertRaises(ValueError):
            suggest_asset_category(
                name="Dell Laptop",
                description=123,
            )

    @patch("workflows.ai_classification.get_gemini_client")
    def test_suggestion_does_not_modify_categories(
        self,
        mock_client,
    ):
        mock_client.return_value = self.mock_gemini({
            "category_id": self.it_category.pk,
            "explanation": "Computer equipment.",
        })

        initial_count = Category.objects.count()

        result = suggest_asset_category(
            name="Dell Laptop",
            description="Programming computer.",
        )

        self.assertEqual(
            Category.objects.count(),
            initial_count,
        )

        self.it_category.refresh_from_db()

        self.assertEqual(
            self.it_category.name,
            "IT Equipment",
        )

        self.assertTrue(result["requires_review"])

    @patch("workflows.ai_classification.get_gemini_client")
    def test_no_categories_available(self, mock_client):
        Category.objects.all().delete()

        result = suggest_asset_category(
            name="Dell Laptop",
        )

        self.assertIsNone(result["category_id"])
        self.assertTrue(result["requires_review"])

        mock_client.assert_not_called()

    @patch("workflows.ai_classification.get_gemini_client")
    def test_explanation_is_limited_to_500_characters(
        self,
        mock_client,
    ):
        mock_client.return_value = self.mock_gemini({
            "category_id": self.it_category.pk,
            "explanation": "A" * 800,
        })

        result = suggest_asset_category(
            name="Dell Laptop",
        )

        self.assertEqual(
            len(result["explanation"]),
            500,
        )
