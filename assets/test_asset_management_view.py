
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


class AssetManagementViewTests(TestCase):

    def setUp(self):
        User = get_user_model()

        custodian_group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian = User.objects.create_user(
            username="management_custodian",
            password="TestPassword123!",
        )
        self.custodian.groups.add(custodian_group)

        self.other_custodian = User.objects.create_user(
            username="management_other_custodian",
            password="TestPassword123!",
        )
        self.other_custodian.groups.add(custodian_group)

        self.non_custodian = User.objects.create_user(
            username="management_regular_user",
            password="TestPassword123!",
        )

        self.department = Department.objects.create(
            name="Management Test Department",
            code="MGMTTEST",
            is_active=True,
        )

        self.category = Category.objects.create(
            name="Management Test Equipment",
        )

        self.published_asset = self.create_asset(
            "Published Monitor",
            "MGMT-001",
            self.custodian,
            Asset.Publication.PUBLISHED,
        )

        self.draft_asset = self.create_asset(
            "Draft Laptop",
            "MGMT-002",
            self.custodian,
            Asset.Publication.DRAFT,
        )

        self.other_asset = self.create_asset(
            "Other Custodian Printer",
            "MGMT-003",
            self.other_custodian,
            Asset.Publication.PUBLISHED,
        )

        self.url = reverse("asset_management")

    def create_asset(
        self,
        name,
        asset_tag,
        custodian,
        publication,
    ):
        asset = Asset.objects.create(
            name=name,
            asset_tag=asset_tag,
            category=self.category,
            department=self.department,
            custodian=custodian,
            location="Test Laboratory",
            tracking_mode=Asset.TrackingMode.INDIVIDUAL,
            quantity=1,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=publication,
        )

        StockBalance.objects.create(
            asset=asset,
            free=1,
        )

        return asset

    # TEST 1: LOGIN REQUIRED

    def test_login_required(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    # TEST 2: NON-CUSTODIAN ACCESS DENIED

    def test_non_custodian_is_forbidden(self):
        self.client.force_login(self.non_custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    # TEST 3: CUSTODIAN CAN ACCESS PAGE

    def test_custodian_can_view_management(self):
        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "assets/management.html",
        )

    # TEST 4: CUSTODIAN SEES ONLY ASSIGNED ASSETS

    def test_only_assigned_assets_are_visible(self):
        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertContains(
            response,
            "Published Monitor",
        )

        self.assertContains(
            response,
            "Draft Laptop",
        )

        self.assertNotContains(
            response,
            "Other Custodian Printer",
        )

        self.assertEqual(
            response.context["total_assets"],
            2,
        )

    # TEST 5: PUBLICATION FILTER WORKS

    def test_publication_filter(self):
        self.client.force_login(self.custodian)

        response = self.client.get(
            self.url,
            {"publication": Asset.Publication.PUBLISHED},
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Published Monitor",
        )

        self.assertNotContains(
            response,
            "Draft Laptop",
        )

        self.assertEqual(
            response.context["total_assets"],
            1,
        )

    # TEST 6: PAGINATION WORKS

    def test_pagination(self):
        for index in range(9):
            self.create_asset(
                f"Extra Asset {index}",
                f"MGMT-EXTRA-{index}",
                self.custodian,
                Asset.Publication.PUBLISHED,
            )

        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["total_assets"],
            11,
        )

        self.assertEqual(
            len(response.context["assets"]),
            10,
        )

        second_page = self.client.get(
            self.url,
            {"page": "2"},
        )

        self.assertEqual(second_page.status_code, 200)

        self.assertEqual(
            len(second_page.context["assets"]),
            1,
        )
