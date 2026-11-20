
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Asset, AssetMaintenance


User = get_user_model()


class MaintenanceCancelViewTests(TestCase):

    def setUp(self):
        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian = User.objects.create_user(
            username="cancel_custodian",
            password="testpass123",
        )
        self.custodian.groups.add(group)

        self.other_custodian = User.objects.create_user(
            username="cancel_other",
            password="testpass123",
        )
        self.other_custodian.groups.add(group)

        self.non_custodian = User.objects.create_user(
            username="cancel_requester",
            password="testpass123",
        )

        self.maintenance_id = 1
        self.url = reverse(
            "maintenance_cancel",
            args=[self.maintenance_id],
        )

    def make_maintenance(self):
        asset = Asset(
            name="Test Laptop",
            custodian=self.custodian,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
        )

        return AssetMaintenance(
            pk=self.maintenance_id,
            asset=asset,
            title="Screen issue",
            quantity=1,
            status=AssetMaintenance.Status.REPORTED,
        )

    def test_anonymous_redirected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_non_custodian_forbidden(self):
        self.client.force_login(self.non_custodian)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_missing_record_returns_404(self):
        self.client.force_login(self.custodian)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    @patch("assets.views.cancel_asset_maintenance")
    @patch("assets.views.get_object_or_404")
    def test_other_custodian_forbidden(
        self, mocked_get, mocked_service
    ):
        self.client.force_login(self.other_custodian)
        mocked_get.return_value = self.make_maintenance()

        response = self.client.post(
            self.url,
            {"reason": "Issue resolved"},
        )

        self.assertEqual(response.status_code, 403)
        mocked_service.assert_not_called()

    @patch("assets.views.get_object_or_404")
    def test_get_displays_form(self, mocked_get):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_maintenance()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "assets/maintenance_cancel.html",
        )

    @patch("assets.views.cancel_asset_maintenance")
    @patch("assets.views.get_object_or_404")
    def test_valid_post_calls_service(
        self, mocked_get, mocked_service
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_maintenance()

        response = self.client.post(
            self.url,
            {"reason": "Issue resolved"},
        )

        self.assertRedirects(
            response,
            reverse("maintenance_management"),
            fetch_redirect_response=False,
        )

        mocked_service.assert_called_once_with(
            actor=self.custodian,
            maintenance_id=self.maintenance_id,
            reason="Issue resolved",
        )

    @patch("assets.views.cancel_asset_maintenance")
    @patch("assets.views.get_object_or_404")
    def test_empty_reason_rejected(
        self, mocked_get, mocked_service
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_maintenance()

        response = self.client.post(
            self.url,
            {"reason": ""},
        )

        self.assertEqual(response.status_code, 200)
        mocked_service.assert_not_called()

    @patch("assets.views.cancel_asset_maintenance")
    @patch("assets.views.get_object_or_404")
    def test_validation_error_displayed(
        self, mocked_get, mocked_service
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_maintenance()

        mocked_service.side_effect = ValidationError(
            "Only reported maintenance can be cancelled."
        )

        response = self.client.post(
            self.url,
            {"reason": "Issue resolved"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Only reported maintenance can be cancelled.",
        )
