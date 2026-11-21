
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from assets.models import AssetInspection


User = get_user_model()


class InspectionCompleteViewTests(TestCase):

    def setUp(self):
        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian = User.objects.create_user(
            username="complete_custodian",
            password="testpass123",
        )
        self.custodian.groups.add(group)

        self.other_custodian = User.objects.create_user(
            username="complete_other",
            password="testpass123",
        )
        self.other_custodian.groups.add(group)

        self.requester = User.objects.create_user(
            username="complete_requester",
            password="testpass123",
        )

        self.inspection_id = 1

        self.url = reverse(
            "inspection_complete",
            args=[self.inspection_id],
        )

        self.valid_data = {
            "findings": "Asset is in good condition.",
            "recommendation": (
                AssetInspection.Recommendation.RETURN_TO_SERVICE
            ),
        }

    def make_inspection(
        self,
        status=AssetInspection.Status.PENDING,
    ):
        asset = SimpleNamespace(
            custodian_id=self.custodian.pk,
            name="Inspection Test Laptop",
            department=SimpleNamespace(
                name="Engineering",
            ),
        )

        return SimpleNamespace(
            pk=self.inspection_id,
            asset=asset,
            quantity=1,
            status=status,
            get_status_display=lambda: status,
        )

    def test_anonymous_user_redirected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_non_custodian_forbidden(self):
        self.client.force_login(self.requester)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_missing_inspection_returns_404(self):
        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    @patch("assets.views.get_object_or_404")
    def test_other_custodian_forbidden(self, mocked_get):
        self.client.force_login(self.other_custodian)

        mocked_get.return_value = self.make_inspection()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    @patch("assets.views.get_object_or_404")
    def test_completed_inspection_redirected(self, mocked_get):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_inspection(
            status=AssetInspection.Status.COMPLETED
        )

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            reverse("inspection_management"),
            fetch_redirect_response=False,
        )

    @patch("assets.views.get_object_or_404")
    def test_get_displays_completion_form(self, mocked_get):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_inspection()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "assets/inspection_complete.html",
        )

        self.assertContains(
            response,
            "Inspection Test Laptop",
        )

    @patch("assets.views.complete_asset_inspection")
    @patch("assets.views.get_object_or_404")
    def test_valid_post_calls_service(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_inspection()

        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertRedirects(
            response,
            reverse("inspection_management"),
            fetch_redirect_response=False,
        )

        mocked_service.assert_called_once_with(
            actor=self.custodian,
            inspection_id=self.inspection_id,
            findings="Asset is in good condition.",
            recommendation=(
                AssetInspection.Recommendation.RETURN_TO_SERVICE
            ),
        )

    @patch("assets.views.complete_asset_inspection")
    @patch("assets.views.get_object_or_404")
    def test_invalid_recommendation_rejected(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_inspection()

        response = self.client.post(
            self.url,
            {
                "findings": "Asset inspected.",
                "recommendation": "InvalidOption",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Select a valid choice.",
        )

        mocked_service.assert_not_called()

    @patch("assets.views.complete_asset_inspection")
    @patch("assets.views.get_object_or_404")
    def test_service_validation_error_displayed(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_inspection()

        mocked_service.side_effect = ValidationError(
            "Only pending inspections can be completed."
        )

        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Only pending inspections can be completed.",
        )
