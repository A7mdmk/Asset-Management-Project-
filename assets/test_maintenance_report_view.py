
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch
from uuid import uuid4

from .models import Asset, AssetMaintenance


User = get_user_model()


class MaintenanceReportViewTests(TestCase):

    def setUp(self):
        self.custodian = User.objects.create_user(
            username="maintenance_custodian",
            password="testpass123",
        )
        self.other_custodian = User.objects.create_user(
            username="maintenance_other",
            password="testpass123",
        )

        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian.groups.add(group)
        self.other_custodian.groups.add(group)

        self.asset_id = uuid4()

        self.url = reverse(
            "maintenance_report",
            args=[self.asset_id],
        )

    def test_anonymous_user_redirected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_missing_asset_returns_404(self):
        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    @patch("assets.views.get_object_or_404")
    def test_other_custodian_cannot_access(
        self,
        mocked_get,
    ):
        self.client.force_login(self.other_custodian)

        asset = Asset(
            id=self.asset_id,
            custodian=self.custodian,
        )

        mocked_get.return_value = asset

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    @patch("assets.views.report_asset_maintenance")
    @patch("assets.views.get_object_or_404")
    def test_valid_report_calls_service(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.custodian)

        asset = Asset(
            id=self.asset_id,
            custodian=self.custodian,
        )

        mocked_get.return_value = asset

        response = self.client.post(
            self.url,
            {
                "title": "Broken screen",
                "description": "Laptop screen is damaged.",
                "quantity": "1",
            },
        )

        self.assertEqual(response.status_code, 302)

        mocked_service.assert_called_once_with(
            actor=self.custodian,
            asset_id=self.asset_id,
            title="Broken screen",
            description="Laptop screen is damaged.",
            quantity=1,
        )

    @patch("assets.views.report_asset_maintenance")
    @patch("assets.views.get_object_or_404")
    def test_invalid_quantity_rejected(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.custodian)

        asset = Asset(
            id=self.asset_id,
            custodian=self.custodian,
        )

        mocked_get.return_value = asset

        response = self.client.post(
            self.url,
            {
                "title": "Broken screen",
                "description": "Laptop screen is damaged.",
                "quantity": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        mocked_service.assert_not_called()

    @patch("assets.views.report_asset_maintenance")
    @patch("assets.views.get_object_or_404")
    def test_empty_description_rejected(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.custodian)

        asset = Asset(
            id=self.asset_id,
            custodian=self.custodian,
        )

        mocked_get.return_value = asset

        response = self.client.post(
            self.url,
            {
                "title": "Broken screen",
                "description": "",
                "quantity": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        mocked_service.assert_not_called()
