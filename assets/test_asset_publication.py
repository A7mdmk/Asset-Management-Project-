
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase

from .asset_search import search_assets
from .models import Asset, Category, Department
from .services import register_asset, change_asset_publication


class AssetPublicationTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.department = Department.objects.create(
            name="Publication Test Department",
            code="PUB-TEST",
        )

        self.category = Category.objects.create(
            name="Publication Test Equipment",
        )

        self.custodian = User.objects.create_user(
            username="publication_custodian",
            password="TestPassword123!",
        )

        self.other_user = User.objects.create_user(
            username="publication_other",
            password="TestPassword123!",
        )

        self.superuser = User.objects.create_superuser(
            username="publication_admin",
            email="publication_admin@example.com",
            password="TestPassword123!",
        )

        custodian_group, _ = Group.objects.get_or_create(
            name="Custodian",
        )

        self.custodian.groups.add(custodian_group)

        self.asset = register_asset(
            name="Publication Test Monitor",
            asset_tag="PUB-001",
            description="Monitor for student projects",
            category=self.category,
            department=self.department,
            custodian=self.custodian,
            location="CS Lab",
            tracking_mode=Asset.TrackingMode.INDIVIDUAL,
            quantity=1,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.DRAFT,
        )

    # TEST 1: SUCCESSFUL PUBLICATION

    def test_custodian_can_publish_draft_asset(self):
        result = change_asset_publication(
            actor=self.custodian,
            asset_id=self.asset.pk,
            publication=Asset.Publication.PUBLISHED,
        )

        result.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            result.publication,
            Asset.Publication.PUBLISHED,
        )
        self.assertEqual(self.asset.stock.free, 1)
        self.assertEqual(self.asset.stock.total, 1)

    # TEST 2: SUCCESSFUL WITHDRAWAL

    def test_custodian_can_withdraw_published_asset(self):
        change_asset_publication(
            actor=self.custodian,
            asset_id=self.asset.pk,
            publication=Asset.Publication.PUBLISHED,
        )

        result = change_asset_publication(
            actor=self.custodian,
            asset_id=self.asset.pk,
            publication=Asset.Publication.WITHDRAWN,
        )

        result.refresh_from_db()

        self.assertEqual(
            result.publication,
            Asset.Publication.WITHDRAWN,
        )

    # TEST 3: UNAUTHORIZED USER

    def test_unauthorized_user_cannot_publish(self):
        with self.assertRaises(ValidationError):
            change_asset_publication(
                actor=self.other_user,
                asset_id=self.asset.pk,
                publication=Asset.Publication.PUBLISHED,
            )

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.publication,
            Asset.Publication.DRAFT,
        )

    # TEST 4: CUSTODIAN ROLE REQUIRED

    def test_custodian_role_is_required(self):
        self.custodian.groups.clear()

        with self.assertRaises(ValidationError):
            change_asset_publication(
                actor=self.custodian,
                asset_id=self.asset.pk,
                publication=Asset.Publication.PUBLISHED,
            )

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.publication,
            Asset.Publication.DRAFT,
        )

    # TEST 5: SUPERUSER CAN PUBLISH

    def test_superuser_can_publish_asset(self):
        result = change_asset_publication(
            actor=self.superuser,
            asset_id=self.asset.pk,
            publication=Asset.Publication.PUBLISHED,
        )

        self.assertEqual(
            result.publication,
            Asset.Publication.PUBLISHED,
        )

    # TEST 6: UNSAFE ASSETS CANNOT BE PUBLISHED

    def test_unsafe_asset_cannot_be_published(self):
        self.asset.condition = Asset.Condition.UNSAFE
        self.asset.save(update_fields=["condition"])

        with self.assertRaises(ValidationError):
            change_asset_publication(
                actor=self.custodian,
                asset_id=self.asset.pk,
                publication=Asset.Publication.PUBLISHED,
            )

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.publication,
            Asset.Publication.DRAFT,
        )

    # TEST 7: RETIRED ASSETS CANNOT BE PUBLISHED

    def test_retired_asset_cannot_be_published(self):
        self.asset.lifecycle = Asset.Lifecycle.RETIRED
        self.asset.save(update_fields=["lifecycle"])

        with self.assertRaises(ValidationError):
            change_asset_publication(
                actor=self.custodian,
                asset_id=self.asset.pk,
                publication=Asset.Publication.PUBLISHED,
            )

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.publication,
            Asset.Publication.DRAFT,
        )

    # TEST 8: DUPLICATE PUBLICATION REJECTED

    def test_duplicate_publication_is_rejected(self):
        change_asset_publication(
            actor=self.custodian,
            asset_id=self.asset.pk,
            publication=Asset.Publication.PUBLISHED,
        )

        with self.assertRaises(ValidationError):
            change_asset_publication(
                actor=self.custodian,
                asset_id=self.asset.pk,
                publication=Asset.Publication.PUBLISHED,
            )

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.publication,
            Asset.Publication.PUBLISHED,
        )

    # TEST 9: WITHDRAWN ASSETS DISAPPEAR FROM SEARCH

    def test_withdrawn_asset_is_excluded_from_search(self):
        change_asset_publication(
            actor=self.custodian,
            asset_id=self.asset.pk,
            publication=Asset.Publication.PUBLISHED,
        )

        self.assertIn(
            self.asset,
            list(search_assets()),
        )

        change_asset_publication(
            actor=self.custodian,
            asset_id=self.asset.pk,
            publication=Asset.Publication.WITHDRAWN,
        )

        self.assertNotIn(
            self.asset,
            list(search_assets()),
        )

    # TEST 10: WITHDRAWAL PRESERVES STOCK

    def test_withdrawal_does_not_move_stock(self):
        change_asset_publication(
            actor=self.custodian,
            asset_id=self.asset.pk,
            publication=Asset.Publication.PUBLISHED,
        )

        change_asset_publication(
            actor=self.custodian,
            asset_id=self.asset.pk,
            publication=Asset.Publication.WITHDRAWN,
        )

        self.asset.stock.refresh_from_db()

        self.assertEqual(self.asset.stock.free, 1)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.in_transit, 0)
        self.assertEqual(self.asset.stock.in_use, 0)
        self.assertEqual(self.asset.stock.blocked, 0)
        self.assertEqual(self.asset.stock.total, 1)

    # TEST 11: INACTIVE USER CANNOT PUBLISH

    def test_inactive_custodian_cannot_publish(self):
        self.custodian.is_active = False
        self.custodian.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            change_asset_publication(
                actor=self.custodian,
                asset_id=self.asset.pk,
                publication=Asset.Publication.PUBLISHED,
            )

        self.asset.refresh_from_db()
        self.assertEqual(
            self.asset.publication,
            Asset.Publication.DRAFT,
        )

    # TEST 12: INACTIVE DEPARTMENT CANNOT PUBLISH

    def test_inactive_department_cannot_publish(self):
        self.department.is_active = False
        self.department.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            change_asset_publication(
                actor=self.custodian,
                asset_id=self.asset.pk,
                publication=Asset.Publication.PUBLISHED,
            )

        self.asset.refresh_from_db()
        self.assertEqual(
            self.asset.publication,
            Asset.Publication.DRAFT,
        )

    # TEST 13: WITHDRAWN ASSET CAN BE REPUBLISHED

    def test_withdrawn_asset_can_be_republished(self):
        change_asset_publication(
            actor=self.custodian,
            asset_id=self.asset.pk,
            publication=Asset.Publication.PUBLISHED,
        )

        change_asset_publication(
            actor=self.custodian,
            asset_id=self.asset.pk,
            publication=Asset.Publication.WITHDRAWN,
        )

        result = change_asset_publication(
            actor=self.custodian,
            asset_id=self.asset.pk,
            publication=Asset.Publication.PUBLISHED,
        )

        result.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            result.publication,
            Asset.Publication.PUBLISHED,
        )
        self.assertIn(result, list(search_assets()))

        self.assertEqual(self.asset.stock.free, 1)
        self.assertEqual(self.asset.stock.total, 1)

    # TEST 14: DATABASE FAILURE ROLLS BACK PUBLICATION

    def test_publication_save_failure_preserves_status(self):
        from unittest.mock import patch

        with patch.object(
            Asset,
            "save",
            side_effect=RuntimeError("Simulated save failure"),
        ):
            with self.assertRaises(RuntimeError):
                change_asset_publication(
                    actor=self.custodian,
                    asset_id=self.asset.pk,
                    publication=Asset.Publication.PUBLISHED,
                )

        self.asset.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            self.asset.publication,
            Asset.Publication.DRAFT,
        )
        self.assertEqual(self.asset.stock.free, 1)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.total, 1)
