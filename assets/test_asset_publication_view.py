
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import (
    Asset,
    Category,
    Department,
    StockBalance,
)


class AssetPublicationViewTests(TestCase):

    def setUp(self):
        User = get_user_model()

        custodian_group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian = User.objects.create_user(
            username="publication_view_custodian",
            password="TestPassword123!",
        )
        self.custodian.groups.add(custodian_group)

        self.other_custodian = User.objects.create_user(
            username="publication_view_other_custodian",
            password="TestPassword123!",
        )
        self.other_custodian.groups.add(custodian_group)

        self.regular_user = User.objects.create_user(
            username="publication_view_regular",
            password="TestPassword123!",
        )

        self.department = Department.objects.create(
            name="Publication View Department",
            code="PUBVIEW",
            is_active=True,
        )

        self.category = Category.objects.create(
            name="Publication View Equipment",
        )

        self.asset = Asset.objects.create(
            name="Publication View Monitor",
            asset_tag="PUBVIEW-001",
            category=self.category,
            department=self.department,
            custodian=self.custodian,
            location="Computer Lab",
            tracking_mode=Asset.TrackingMode.INDIVIDUAL,
            quantity=1,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.DRAFT,
        )

        StockBalance.objects.create(
            asset=self.asset,
            free=1,
        )

        self.url = reverse(
            "asset_publication",
            args=[self.asset.pk],
        )

    # TEST 1: LOGIN REQUIRED

    def test_login_required(self):
        response = self.client.post(
            self.url,
            {"action": "publish"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    # TEST 2: NON-CUSTODIAN CANNOT PUBLISH

    def test_non_custodian_cannot_publish(self):
        self.client.force_login(self.regular_user)

        response = self.client.post(
            self.url,
            {"action": "publish"},
        )

        self.assertEqual(response.status_code, 403)

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.publication,
            Asset.Publication.DRAFT,
        )

    # TEST 3: CUSTODIAN CANNOT MANAGE ANOTHER ASSET

    def test_other_custodian_cannot_publish(self):
        self.client.force_login(self.other_custodian)

        response = self.client.post(
            self.url,
            {"action": "publish"},
        )

        self.assertEqual(response.status_code, 403)

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.publication,
            Asset.Publication.DRAFT,
        )

    # TEST 4: GET CANNOT CHANGE PUBLICATION

    def test_get_does_not_change_publication(self):
        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            reverse("asset_management"),
        )

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.publication,
            Asset.Publication.DRAFT,
        )

    # TEST 5: INVALID ACTION IS REJECTED

    def test_invalid_action_is_forbidden(self):
        self.client.force_login(self.custodian)

        response = self.client.post(
            self.url,
            {"action": "delete"},
        )

        self.assertEqual(response.status_code, 403)

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.publication,
            Asset.Publication.DRAFT,
        )

    # TEST 6: CUSTODIAN CAN PUBLISH

    def test_custodian_can_publish_asset(self):
        self.client.force_login(self.custodian)

        response = self.client.post(
            self.url,
            {"action": "publish"},
        )

        self.assertRedirects(
            response,
            reverse("asset_management"),
        )

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.publication,
            Asset.Publication.PUBLISHED,
        )

        stock = StockBalance.objects.get(asset=self.asset)

        self.assertEqual(stock.free, 1)
        self.assertEqual(stock.held, 0)

    # TEST 7: CUSTODIAN CAN WITHDRAW

    def test_custodian_can_withdraw_asset(self):
        self.asset.publication = Asset.Publication.PUBLISHED
        self.asset.save(update_fields=["publication"])

        self.client.force_login(self.custodian)

        response = self.client.post(
            self.url,
            {"action": "withdraw"},
        )

        self.assertRedirects(
            response,
            reverse("asset_management"),
        )

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.publication,
            Asset.Publication.WITHDRAWN,
        )

        stock = StockBalance.objects.get(asset=self.asset)

        self.assertEqual(stock.free, 1)

    # TEST 8: UNSAFE ASSET CANNOT BE PUBLISHED

    def test_unsafe_asset_cannot_be_published(self):
        self.asset.condition = Asset.Condition.UNSAFE
        self.asset.save(update_fields=["condition"])

        self.client.force_login(self.custodian)

        response = self.client.post(
            self.url,
            {"action": "publish"},
        )

        self.assertEqual(response.status_code, 400)

        self.assertTemplateUsed(
            response,
            "assets/publication_error.html",
        )

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.publication,
            Asset.Publication.DRAFT,
        )

    # TEST 9: RETIRED ASSET CANNOT BE PUBLISHED

    def test_retired_asset_cannot_be_published(self):
        self.asset.lifecycle = Asset.Lifecycle.RETIRED
        self.asset.save(update_fields=["lifecycle"])

        self.client.force_login(self.custodian)

        response = self.client.post(
            self.url,
            {"action": "publish"},
        )

        self.assertEqual(response.status_code, 400)

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.publication,
            Asset.Publication.DRAFT,
        )
