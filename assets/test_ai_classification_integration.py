
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from assets.models import Asset, Category


User = get_user_model()


class AIClassificationIntegrationTests(TestCase):

    def setUp(self):
        self.registration_url = reverse(
            "asset_registration"
        )
        self.classification_url = reverse(
            "ai_classification"
        )

        self.custodian = User.objects.create_user(
            username="ai_integration_custodian",
            password="TestPassword123!",
        )

        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )
        self.custodian.groups.add(group)

        self.category = Category.objects.create(
            name="IT Equipment",
            description="Computers and electronics",
        )

        self.client.force_login(self.custodian)

    def test_registration_name_is_prefilled(self):
        response = self.client.get(
            self.registration_url,
            {"name": "Dell Laptop"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].initial["name"],
            "Dell Laptop",
        )

    def test_registration_description_is_prefilled(self):
        response = self.client.get(
            self.registration_url,
            {"description": "Laptop for programming"},
        )

        self.assertEqual(
            response.context["form"].initial["description"],
            "Laptop for programming",
        )

    def test_valid_suggested_category_is_prefilled(self):
        response = self.client.get(
            self.registration_url,
            {
                "name": "Dell Laptop",
                "suggested_category": str(self.category.pk),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].initial["category"],
            self.category.pk,
        )

    def test_invalid_category_id_is_ignored(self):
        response = self.client.get(
            self.registration_url,
            {"suggested_category": "999999"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            "category",
            response.context["form"].initial,
        )

    def test_non_numeric_category_id_is_ignored(self):
        response = self.client.get(
            self.registration_url,
            {"suggested_category": "invalid"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            "category",
            response.context["form"].initial,
        )

    def test_oversized_name_is_not_prefilled(self):
        response = self.client.get(
            self.registration_url,
            {"name": "A" * 121},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            "name",
            response.context["form"].initial,
        )

    def test_get_suggestion_does_not_create_asset(self):
        original_count = Asset.objects.count()

        response = self.client.get(
            self.registration_url,
            {
                "name": "Dell Laptop",
                "description": "Programming laptop",
                "suggested_category": str(self.category.pk),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Asset.objects.count(),
            original_count,
        )

    @patch("assets.views.suggest_asset_category")
    def test_classification_page_displays_apply_button(
        self,
        mock_suggest,
    ):
        mock_suggest.return_value = {
            "category_id": self.category.pk,
            "category_name": "IT Equipment",
            "explanation": "This is computer equipment.",
            "requires_review": True,
        }

        response = self.client.post(
            self.classification_url,
            {
                "asset_name": "Dell Laptop",
                "description": "Programming laptop",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Use This Suggestion",
        )
        self.assertContains(
            response,
            'name="suggested_category"',
        )
        self.assertEqual(
            Asset.objects.count(),
            0,
        )
