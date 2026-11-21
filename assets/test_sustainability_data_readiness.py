
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from assets.models import Asset, Category, Department
from assets.services import register_asset
from assets.sustainability_services import (
    get_sustainability_data_readiness,
)


User = get_user_model()


class SustainabilityDataReadinessTests(TestCase):

    def setUp(self):
        self.custodian = User.objects.create_user(
            username="readiness_custodian",
            password="TestPassword123!",
        )

        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )
        self.custodian.groups.add(group)

        self.department = Department.objects.create(
            name="Readiness Engineering",
            code="RDYENG",
        )

        self.category = Category.objects.create(
            name="Readiness Equipment",
        )

    def create_asset(self, name):
        return register_asset(
            name=name,
            category=self.category,
            department=self.department,
            custodian=self.custodian,
            location="Engineering Lab",
            tracking_mode=Asset.TrackingMode.LOT,
            quantity=5,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.PUBLISHED,
        )

    def test_empty_database(self):
        result = get_sustainability_data_readiness()

        self.assertEqual(result["total_assets"], 0)
        self.assertEqual(result["assets_with_value"], 0)
        self.assertEqual(result["assets_with_mass"], 0)
        self.assertEqual(result["assets_with_both"], 0)
        self.assertEqual(result["assets_missing_value"], 0)
        self.assertEqual(result["assets_missing_mass"], 0)

    def test_asset_missing_both_measurements(self):
        self.create_asset("Laptop A")

        result = get_sustainability_data_readiness()

        self.assertEqual(result["total_assets"], 1)
        self.assertEqual(result["assets_with_value"], 0)
        self.assertEqual(result["assets_with_mass"], 0)
        self.assertEqual(result["assets_with_both"], 0)
        self.assertEqual(result["assets_missing_value"], 1)
        self.assertEqual(result["assets_missing_mass"], 1)

    def test_asset_with_financial_value_only(self):
        asset = self.create_asset("Laptop B")

        asset.estimated_value_aed = Decimal("2500.00")
        asset.save(update_fields=["estimated_value_aed"])

        result = get_sustainability_data_readiness()

        self.assertEqual(result["assets_with_value"], 1)
        self.assertEqual(result["assets_with_mass"], 0)
        self.assertEqual(result["assets_with_both"], 0)
        self.assertEqual(result["assets_missing_value"], 0)
        self.assertEqual(result["assets_missing_mass"], 1)

    def test_asset_with_mass_only(self):
        asset = self.create_asset("Laptop C")

        asset.mass_kg = Decimal("2.500")
        asset.save(update_fields=["mass_kg"])

        result = get_sustainability_data_readiness()

        self.assertEqual(result["assets_with_value"], 0)
        self.assertEqual(result["assets_with_mass"], 1)
        self.assertEqual(result["assets_with_both"], 0)
        self.assertEqual(result["assets_missing_value"], 1)
        self.assertEqual(result["assets_missing_mass"], 0)

    def test_asset_with_both_measurements(self):
        asset = self.create_asset("Laptop D")

        asset.estimated_value_aed = Decimal("3500.00")
        asset.mass_kg = Decimal("3.200")

        asset.save(
            update_fields=[
                "estimated_value_aed",
                "mass_kg",
            ]
        )

        result = get_sustainability_data_readiness()

        self.assertEqual(result["total_assets"], 1)
        self.assertEqual(result["assets_with_value"], 1)
        self.assertEqual(result["assets_with_mass"], 1)
        self.assertEqual(result["assets_with_both"], 1)
        self.assertEqual(result["assets_missing_value"], 0)
        self.assertEqual(result["assets_missing_mass"], 0)

    def test_mixed_asset_records(self):
        first = self.create_asset("Laptop E")
        second = self.create_asset("Laptop F")
        third = self.create_asset("Laptop G")

        first.estimated_value_aed = Decimal("1500.00")
        first.save(update_fields=["estimated_value_aed"])

        second.mass_kg = Decimal("4.000")
        second.save(update_fields=["mass_kg"])

        third.estimated_value_aed = Decimal("2200.00")
        third.mass_kg = Decimal("2.000")
        third.save(
            update_fields=[
                "estimated_value_aed",
                "mass_kg",
            ]
        )

        result = get_sustainability_data_readiness()

        self.assertEqual(result["total_assets"], 3)
        self.assertEqual(result["assets_with_value"], 2)
        self.assertEqual(result["assets_with_mass"], 2)
        self.assertEqual(result["assets_with_both"], 1)
        self.assertEqual(result["assets_missing_value"], 1)
        self.assertEqual(result["assets_missing_mass"], 1)

    @patch(
        "assets.views.get_sustainability_data_readiness"
    )
    def test_dashboard_displays_readiness(self, mock_readiness):
        mock_readiness.return_value = {
            "total_assets": 4,
            "assets_with_value": 3,
            "assets_with_mass": 2,
            "assets_with_both": 1,
            "assets_missing_value": 1,
            "assets_missing_mass": 2,
        }

        self.client.force_login(self.custodian)

        response = self.client.get(
            reverse("sustainability_dashboard")
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["readiness"]["assets_with_value"],
            3,
        )

        self.assertContains(
            response,
            "Data Readiness",
        )

        self.assertContains(
            response,
            "Assets With Financial Values",
        )

        mock_readiness.assert_called_once_with()
