
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AIRecommendationViewTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ai_view_test_user",
            password="TestPassword123!",
        )
        self.url = reverse("ai_recommendations")

    def test_login_required(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_authenticated_user_can_open_page(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "workflows/recommendations.html",
        )

    def test_empty_request_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {"user_need": "   "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Please describe the resource you need.",
        )

    def test_request_over_500_characters_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {"user_need": "A" * 501},
        )

        self.assertContains(
            response,
            "Your request must be 500 characters or fewer.",
        )

    @patch("workflows.views.recommend_assets")
    def test_recommendations_are_displayed(self, mock_recommend):
        mock_recommend.return_value = {
            "recommendations": [
                {
                    "id": "test-asset-id",
                    "name": "Dell Monitor",
                    "description": "24-inch display",
                    "category": "IT Equipment",
                    "department": "Computer Science",
                    "location": "CS Lab",
                    "available_quantity": 1,
                }
            ],
            "message": "Recommendations generated successfully.",
        }

        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {"user_need": "I need a monitor"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dell Monitor")
        self.assertContains(response, "Computer Science")
        self.assertContains(response, "CS Lab")
        mock_recommend.assert_called_once_with(
            "I need a monitor"
        )

    @patch("workflows.views.recommend_assets")
    def test_api_failure_displays_safe_error(self, mock_recommend):
        mock_recommend.side_effect = RuntimeError(
            "Internal API error"
        )

        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {"user_need": "I need a laptop"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "AI recommendations are temporarily unavailable.",
        )
        self.assertNotContains(
            response,
            "Internal API error",
        )
