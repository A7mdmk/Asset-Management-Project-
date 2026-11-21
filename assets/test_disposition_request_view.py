
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from assets.models import (
    Asset,
    AssetInspection,
    AssetDisposition,
)


User = get_user_model()


class DispositionRequestViewTests(TestCase):

    def setUp(self):
        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian = User.objects.create_user(
            username="disposition_custodian",
            password="testpass123",
        )
        self.custodian.groups.add(group)

        self.other_custodian = User.objects.create_user(
            username="disposition_other",
            password="testpass123",
        )
        self.other_custodian.groups.add(group)

        self.requester = User.objects.create_user(
            username="disposition_requester",
            password="testpass123",
        )

        self.inspection_id = 1
        self.url = reverse(
            "disposition_request",
            args=[self.inspection_id],
        )

        self.valid_reason = (
            "Asset has reached the end of its useful life."
        )

    def make_inspection(
        self,
        status=AssetInspection.Status.COMPLETED,
        recommendation=AssetInspection.Recommendation.RETIRE,
        lifecycle=Asset.Lifecycle.ACTIVE,
    ):
        asset = SimpleNamespace(
            custodian_id=self.custodian.pk,
            lifecycle=lifecycle,
            name="Disposition Test Laptop",
        )

        return SimpleNamespace(
            pk=self.inspection_id,
            asset=asset,
            quantity=1,
            status=status,
            recommendation=recommendation,
            get_recommendation_display=lambda: "Retire",
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
    def test_pending_inspection_forbidden(self, mocked_get):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_inspection(
            status=AssetInspection.Status.PENDING,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    @patch("assets.views.get_object_or_404")
    def test_ineligible_recommendation_forbidden(
        self,
        mocked_get,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_inspection(
            recommendation=AssetInspection.Recommendation.REPAIR,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    @patch("assets.views.get_object_or_404")
    def test_retired_asset_forbidden(self, mocked_get):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_inspection(
            lifecycle=Asset.Lifecycle.RETIRED,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    @patch("assets.views.get_object_or_404")
    def test_get_displays_request_form(self, mocked_get):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_inspection()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "assets/disposition_request.html",
        )

        self.assertContains(
            response,
            "Disposition Test Laptop",
        )

    @patch("assets.views.request_asset_disposition")
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
            {"reason": self.valid_reason},
        )

        self.assertRedirects(
            response,
            reverse("disposition_management"),
            fetch_redirect_response=False,
        )

        mocked_service.assert_called_once_with(
            actor=self.custodian,
            inspection_id=self.inspection_id,
            disposition_type=(
                AssetDisposition.DispositionType.RETIRED
            ),
            reason=self.valid_reason,
        )

    @patch("assets.views.request_asset_disposition")
    @patch("assets.views.get_object_or_404")
    def test_duplicate_disposition_error_displayed(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_inspection()

        mocked_service.side_effect = ValidationError(
            "A disposition already exists for this inspection."
        )

        response = self.client.post(
            self.url,
            {"reason": self.valid_reason},
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "A disposition already exists for this inspection.",
        )
