
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import Asset, Category, Department, StockBalance
from .services import register_asset


class AssetRegistrationTests(TestCase):

    def setUp(self):
        self.department = Department.objects.create(
            name="Computer Science",
            code="CS",
        )
        self.category = Category.objects.create(
            name="IT Equipment"
        )
        self.custodian = get_user_model().objects.create_user(
            username="test_custodian",
            password="TestPassword123!"
        )

        self.asset_data = {
            "name": "Dell Monitor",
            "asset_tag": "TEST-001",
            "category": self.category,
            "department": self.department,
            "custodian": self.custodian,
            "location": "CS Lab 101",
            "tracking_mode": Asset.TrackingMode.INDIVIDUAL,
            "quantity": 1,
            "condition": Asset.Condition.GOOD,
            "lifecycle": Asset.Lifecycle.ACTIVE,
            "publication": Asset.Publication.DRAFT,
        }

    def test_register_asset_creates_one_stock_balance(self):
        asset = register_asset(**self.asset_data)

        self.assertEqual(
            StockBalance.objects.filter(asset=asset).count(), 1
        )
        self.assertEqual(asset.stock.free, 1)
        self.assertEqual(asset.stock.total, 1)

    def test_individual_asset_cannot_have_quantity_two(self):
        self.asset_data["quantity"] = 2

        with self.assertRaises(ValidationError):
            register_asset(**self.asset_data)

        self.assertEqual(Asset.objects.count(), 0)
        self.assertEqual(StockBalance.objects.count(), 0)

    def test_unsafe_asset_is_blocked(self):
        self.asset_data["condition"] = Asset.Condition.UNSAFE

        asset = register_asset(**self.asset_data)

        self.assertEqual(asset.stock.free, 0)
        self.assertEqual(asset.stock.blocked, 1)
        self.assertEqual(asset.stock.total, 1)

    def test_lot_quantity_is_preserved(self):
        self.asset_data["tracking_mode"] = Asset.TrackingMode.LOT
        self.asset_data["quantity"] = 10

        asset = register_asset(**self.asset_data)

        self.assertEqual(asset.stock.free, 10)
        self.assertEqual(asset.stock.total, 10)

    def test_duplicate_asset_tag_is_rejected(self):
        register_asset(**self.asset_data)

        with self.assertRaises(ValidationError):
            register_asset(**self.asset_data)

        self.assertEqual(Asset.objects.count(), 1)
        self.assertEqual(StockBalance.objects.count(), 1)

    def test_inactive_department_is_rejected(self):
        self.department.is_active = False
        self.department.save()

        with self.assertRaises(ValidationError):
            register_asset(**self.asset_data)

        self.assertEqual(Asset.objects.count(), 0)

    def test_stock_must_equal_asset_quantity(self):
        asset = register_asset(**self.asset_data)

        asset.stock.free = 0

        with self.assertRaises(ValidationError):
            asset.stock.full_clean()
