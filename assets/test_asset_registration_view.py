
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import (
    Asset,
    Category,
    Department,
    StockBalance,
    StockMovement,
)


class AssetRegistrationViewTests(TestCase):

    def setUp(self):
        User = get_user_model()

        custodian_group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian = User.objects.create_user(
            username="registration_custodian",
            password="TestPassword123!",
        )
        self.custodian.groups.add(custodian_group)

        self.other_user = User.objects.create_user(
            username="registration_other_user",
            password="TestPassword123!",
        )

        self.department = Department.objects.create(
            name="Registration Test Department",
            code="REGTEST",
            is_active=True,
        )

        self.category = Category.objects.create(
            name="Registration Test Equipment",
        )

        self.url = reverse("asset_registration")

        self.valid_data = {
            "name": "Registration Test Laptop",
            "description": "Laptop for campus use.",
            "asset_tag": "REG-TEST-001",
            "category": str(self.category.pk),
            "department": str(self.department.pk),
            "location": "Computer Laboratory",
            "tracking_mode": Asset.TrackingMode.INDIVIDUAL,
            "quantity": "1",
            "condition": Asset.Condition.GOOD,
        }

    # TEST 1: LOGIN REQUIRED

    def test_login_required(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    # TEST 2: NON-CUSTODIAN CANNOT REGISTER

    def test_non_custodian_is_forbidden(self):
        self.client.force_login(self.other_user)

        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Asset.objects.count(), 0)

    # TEST 3: CUSTODIAN CAN OPEN FORM

    def test_custodian_can_open_registration_form(self):
        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "assets/register.html",
        )

    # TEST 4: VALID REGISTRATION CREATES ASSET

    def test_valid_registration_creates_asset(self):
        self.client.force_login(self.custodian)

        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertRedirects(
            response,
            reverse("asset_management"),
        )

        asset = Asset.objects.get(
            asset_tag="REG-TEST-001"
        )

        self.assertEqual(asset.custodian, self.custodian)
        self.assertEqual(
            asset.publication,
            Asset.Publication.DRAFT,
        )
        self.assertEqual(
            asset.lifecycle,
            Asset.Lifecycle.ACTIVE,
        )
        self.assertEqual(asset.quantity, 1)

    # TEST 5: STOCK AND MOVEMENT ARE INITIALIZED

    def test_registration_initializes_stock_and_history(self):
        self.client.force_login(self.custodian)

        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertEqual(response.status_code, 302)

        asset = Asset.objects.get(
            asset_tag="REG-TEST-001"
        )

        stock = StockBalance.objects.get(asset=asset)

        self.assertEqual(stock.free, 1)
        self.assertEqual(stock.blocked, 0)

        movement = StockMovement.objects.get(asset=asset)

        self.assertEqual(
            movement.movement_type,
            StockMovement.MovementType.REGISTRATION,
        )
        self.assertEqual(movement.quantity, 1)
        self.assertEqual(movement.source, "")
        self.assertEqual(
            movement.destination,
            StockMovement.Bucket.FREE,
        )

    # TEST 6: USER CANNOT FORGE OWNERSHIP OR PUBLICATION

    def test_forged_custodian_and_publication_are_ignored(self):
        self.client.force_login(self.custodian)

        data = {
            **self.valid_data,
            "custodian": str(self.other_user.pk),
            "publication": Asset.Publication.PUBLISHED,
            "lifecycle": Asset.Lifecycle.RETIRED,
        }

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 302)

        asset = Asset.objects.get(
            asset_tag="REG-TEST-001"
        )

        self.assertEqual(asset.custodian, self.custodian)
        self.assertEqual(
            asset.publication,
            Asset.Publication.DRAFT,
        )
        self.assertEqual(
            asset.lifecycle,
            Asset.Lifecycle.ACTIVE,
        )

    # TEST 7: INVALID INDIVIDUAL QUANTITY REJECTED

    def test_individual_asset_rejects_multiple_units(self):
        self.client.force_login(self.custodian)

        data = {
            **self.valid_data,
            "quantity": "3",
        }

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(Asset.objects.count(), 0)

    # TEST 8: UNSAFE ASSET STARTS BLOCKED

    def test_unsafe_asset_starts_with_blocked_stock(self):
        self.client.force_login(self.custodian)

        data = {
            **self.valid_data,
            "condition": Asset.Condition.UNSAFE,
        }

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 302)

        asset = Asset.objects.get(
            asset_tag="REG-TEST-001"
        )

        stock = StockBalance.objects.get(asset=asset)

        self.assertEqual(stock.free, 0)
        self.assertEqual(stock.blocked, 1)

        movement = StockMovement.objects.get(asset=asset)

        self.assertEqual(
            movement.destination,
            StockMovement.Bucket.BLOCKED,
        )

        self.assertEqual(
            asset.publication,
            Asset.Publication.DRAFT,
        )

