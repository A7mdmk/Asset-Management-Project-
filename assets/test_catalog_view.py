
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Asset


class AssetCatalogViewTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="catalog_test_user",
            password="TestPassword123!",
        )

        self.url = reverse("asset_catalog")

    # TEST 1: LOGIN REQUIRED

    def test_catalog_requires_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    # TEST 2: LOGGED-IN USER CAN OPEN THE CATALOG

    def test_authenticated_user_can_view_catalog(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "assets/catalog.html",
        )

    # TEST 3: SEARCH TEXT REACHES THE BACKEND SERVICE

    @patch("assets.views.search_assets")
    def test_search_query_passed_to_service(self, mock_search):
        mock_search.return_value = Asset.objects.none()

        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {"q": "Dell Monitor"},
        )

        self.assertEqual(response.status_code, 200)

        mock_search.assert_called_once_with(
            query="Dell Monitor",
            category_id=None,
            department_id=None,
            condition=None,
            available_only=True,
        )

    # TEST 4: VALID FILTERS ARE PASSED CORRECTLY

    @patch("assets.views.search_assets")
    def test_catalog_filters(self, mock_search):
        mock_search.return_value = Asset.objects.none()

        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "category": "2",
                "department": "3",
                "condition": "Good",
                "available": "0",
            },
        )

        self.assertEqual(response.status_code, 200)

        mock_search.assert_called_once_with(
            query="",
            category_id=2,
            department_id=3,
            condition="Good",
            available_only=False,
        )

    # TEST 5: INVALID FILTER VALUES ARE IGNORED

    @patch("assets.views.search_assets")
    def test_invalid_filters_are_ignored(self, mock_search):
        mock_search.return_value = Asset.objects.none()

        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "category": "invalid",
                "department": "abc",
                "condition": "Unsafe",
            },
        )

        self.assertEqual(response.status_code, 200)

        mock_search.assert_called_once_with(
            query="",
            category_id=None,
            department_id=None,
            condition=None,
            available_only=True,
        )
