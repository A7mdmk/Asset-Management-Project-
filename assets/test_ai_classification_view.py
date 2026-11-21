
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from assets.models import Category


User = get_user_model()


class AIClassificationViewTests(TestCase):

    def setUp(self):
        self.url = reverse("ai_classification")

        self.custodian = User.objects.create_user(
            username="classification_custodian",
            password="TestPassword123!",
        )

        self.requester = User.objects.create_user(
            username="classification_requester",
            password="TestPassword123!",
        )

        custodian_group, _ = Group.objects.get_or_create(
            name="Custodian"
        )
        requester_group, _ = Group.objects.get_or_create(
            name="Requester"
        )

        self.custodian.groups.add(custodian_group)
        self.requester.groups.add(requester_group)

        self.category = Category.objects.create(
            name="IT Equipment",
            description="Computers and electronic equipment",
        )

    def test_anonymous_user_redirected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_requester_cannot_access(self):
        self.client.force_login(self.requester)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_custodian_can_open_page(self):
        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "AI-Assisted Asset Classification",
        )

    def test_get_request_does_not_call_gemini(self):
        self.client.force_login(self.custodian)

        with patch(
            "assets.views.suggest_asset_category"
        ) as mock_suggest:
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        mock_suggest.assert_not_called()

    @patch("assets.views.suggest_asset_category")
    def test_valid_submission(self, mock_suggest):
        mock_suggest.return_value = {
            "category_id": self.category.pk,
            "category_name": "IT Equipment",
            "explanation": "This asset is a computer.",
            "requires_review": True,
        }

        self.client.force_login(self.custodian)

        response = self.client.post(
            self.url,
            {
                "asset_name": "Dell Laptop",
                "description": "Programming laptop",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "IT Equipment")
        self.assertContains(
            response,
            "This asset is a computer.",
        )

        mock_suggest.assert_called_once_with(
            name="Dell Laptop",
            description="Programming laptop",
        )

    @patch("assets.views.suggest_asset_category")
    def test_empty_name_rejected(self, mock_suggest):
        self.client.force_login(self.custodian)

        response = self.client.post(
            self.url,
            {
                "asset_name": "   ",
                "description": "Laptop",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Please enter an asset name.",
        )

        mock_suggest.assert_not_called()

    @patch("assets.views.suggest_asset_category")
    def test_long_name_rejected(self, mock_suggest):
        self.client.force_login(self.custodian)

        response = self.client.post(
            self.url,
            {
                "asset_name": "A" * 121,
                "description": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Asset name cannot exceed 120 characters.",
        )

        mock_suggest.assert_not_called()

    @patch("assets.views.suggest_asset_category")
    def test_long_description_rejected(self, mock_suggest):
        self.client.force_login(self.custodian)

        response = self.client.post(
            self.url,
            {
                "asset_name": "Laptop",
                "description": "A" * 2001,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Description cannot exceed 2000 characters.",
        )

        mock_suggest.assert_not_called()

    @patch("assets.views.suggest_asset_category")
    def test_gemini_failure_is_handled(self, mock_suggest):
        mock_suggest.side_effect = ValueError(
            "Gemini service unavailable."
        )

        self.client.force_login(self.custodian)

        response = self.client.post(
            self.url,
            {
                "asset_name": "Dell Laptop",
                "description": "Programming laptop",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "AI classification is temporarily unavailable.",
        )

    @patch("assets.views.suggest_asset_category")
    def test_suggestion_does_not_create_category(
        self,
        mock_suggest,
    ):
        mock_suggest.return_value = {
            "category_id": self.category.pk,
            "category_name": "IT Equipment",
            "explanation": "Computer equipment.",
            "requires_review": True,
        }

        self.client.force_login(self.custodian)

        original_count = Category.objects.count()

        response = self.client.post(
            self.url,
            {
                "asset_name": "Dell Laptop",
                "description": "Laptop for programming",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            Category.objects.count(),
            original_count,
        )
