
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Asset, AssetMaintenance


User = get_user_model()


class MaintenanceStartViewTests(TestCase):

    def setUp(self):
        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian = User.objects.create_user(
            username="start_custodian",
            password="testpass123",
        )
        self.custodian.groups.add(group)

        self.other_custodian = User.objects.create_user(
            username="start_other",
            password="testpass123",
        )
        self.other_custodian.groups.add(group)

        self.non_custodian = User.objects.create_user(
            username="start_requester",
            password="testpass123",
        )

        self.maintenance_id = 1

        self.url = reverse(
            "maintenance_start",
            args=[self.maintenance_id],
        )

    def make_maintenance(self, custodian=None):
        asset = Asset(
            custodian=custodian or self.custodian
        )

        maintenance = AssetMaintenance(
            pk=self.maintenance_id,
            asset=asset,
            title="Broken laptop screen",
            status=AssetMaintenance.Status.REPORTED,
        )

        return maintenance

    def test_anonymous_user_redirected(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)

    def test_non_custodian_forbidden(self):
        self.client.force_login(self.non_custodian)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)

    def test_missing_maintenance_returns_404(self):
        self.client.force_login(self.custodian)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 404)

    @patch("assets.views.start_asset_repair")
    @patch("assets.views.get_object_or_404")
    def test_other_custodian_forbidden(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.other_custodian)

        mocked_get.return_value = self.make_maintenance()

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        mocked_service.assert_not_called()

    @patch("assets.views.start_asset_repair")
    @patch("assets.views.get_object_or_404")
    def test_get_does_not_start_repair(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_maintenance()

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            reverse("maintenance_management"),
            fetch_redirect_response=False,
        )

        mocked_service.assert_not_called()

    @patch("assets.views.start_asset_repair")
    @patch("assets.views.get_object_or_404")
    def test_valid_post_calls_service(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_maintenance()

        response = self.client.post(self.url)

        self.assertRedirects(
            response,
            reverse("maintenance_management"),
            fetch_redirect_response=False,
        )

        mocked_service.assert_called_once_with(
            actor=self.custodian,
            maintenance_id=self.maintenance_id,
        )

    @patch("assets.views.start_asset_repair")
    @patch("assets.views.get_object_or_404")
    def test_service_validation_error_returns_400(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_maintenance()

        mocked_service.side_effect = ValidationError(
            "Only reported maintenance can be started."
        )

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response,
            "Only reported maintenance can be started.",
            status_code=400,
        )
