
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import (
    Asset,
    AssetInspection,
    AssetDisposition,
    Category,
    Department,
    StockBalance,
)

from .services import (
    register_asset,
    request_asset_inspection,
    complete_asset_inspection,
    cancel_asset_inspection,
    request_asset_disposition,
    execute_asset_disposition,
    cancel_asset_disposition,
    report_asset_maintenance,
)


class AssetInspectionDispositionTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.department = Department.objects.create(
            name="Inspection Test Department",
            code="INSP-TEST",
        )

        self.category = Category.objects.create(
            name="Inspection Test Equipment",
        )

        self.custodian = User.objects.create_user(
            username="inspection_custodian",
            password="TestPassword123!",
        )

        self.other_user = User.objects.create_user(
            username="inspection_other",
            password="TestPassword123!",
        )

        self.admin = User.objects.create_superuser(
            username="inspection_admin",
            email="inspection_admin@example.com",
            password="TestPassword123!",
        )

        group, _ = Group.objects.get_or_create(
            name="Custodian",
        )
        self.custodian.groups.add(group)

        self.asset = register_asset(
            name="Inspection Test Laptops",
            asset_tag="INSP-001",
            description="Equipment for inspection testing",
            category=self.category,
            department=self.department,
            custodian=self.custodian,
            location="CS Laboratory",
            tracking_mode=Asset.TrackingMode.LOT,
            quantity=10,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.PUBLISHED,
        )

    def request_inspection(self, quantity=2, actor=None):
        return request_asset_inspection(
            actor=actor or self.custodian,
            asset_id=self.asset.pk,
            quantity=quantity,
        )

    def complete_inspection(
        self,
        inspection,
        recommendation=AssetInspection.Recommendation.RECYCLE,
        actor=None,
    ):
        return complete_asset_inspection(
            actor=actor or self.custodian,
            inspection_id=inspection.pk,
            findings="Equipment inspected and assessed",
            recommendation=recommendation,
        )

    def prepare_disposition(
        self,
        quantity=2,
        recommendation=AssetInspection.Recommendation.RECYCLE,
        disposition_type=AssetDisposition.DispositionType.RECYCLED,
    ):
        inspection = self.request_inspection(quantity)
        self.complete_inspection(
            inspection,
            recommendation=recommendation,
        )

        return request_asset_disposition(
            actor=self.custodian,
            inspection_id=inspection.pk,
            disposition_type=disposition_type,
            reason="Equipment is no longer suitable for use",
        )

    def execute(self, disposition, actor=None):
        return execute_asset_disposition(
            actor=actor or self.custodian,
            disposition_id=disposition.pk,
            completion_notes="Disposition completed and recorded",
        )

    def check_stock(
        self,
        *,
        free,
        retired=0,
        blocked=0,
        held=0,
        in_transit=0,
        in_use=0,
    ):
        stock = StockBalance.objects.get(asset=self.asset)

        self.assertEqual(stock.free, free)
        self.assertEqual(stock.retired, retired)
        self.assertEqual(stock.blocked, blocked)
        self.assertEqual(stock.held, held)
        self.assertEqual(stock.in_transit, in_transit)
        self.assertEqual(stock.in_use, in_use)
        self.assertEqual(stock.total, 10)

    # TEST 1: CREATE INSPECTION

    def test_request_inspection(self):
        inspection = self.request_inspection()

        self.assertEqual(
            inspection.status,
            AssetInspection.Status.PENDING,
        )
        self.assertEqual(inspection.quantity, 2)
        self.check_stock(free=10)

    # TEST 2: COMPLETE INSPECTION

    def test_complete_inspection(self):
        inspection = self.request_inspection()

        result = self.complete_inspection(inspection)

        self.assertEqual(
            result.status,
            AssetInspection.Status.COMPLETED,
        )
        self.assertEqual(
            result.recommendation,
            AssetInspection.Recommendation.RECYCLE,
        )
        self.assertIsNotNone(result.inspected_at)
        self.check_stock(free=10)

    # TEST 3: CANCEL PENDING INSPECTION

    def test_cancel_pending_inspection(self):
        inspection = self.request_inspection()

        result = cancel_asset_inspection(
            actor=self.custodian,
            inspection_id=inspection.pk,
        )

        self.assertEqual(
            result.status,
            AssetInspection.Status.CANCELLED,
        )
        self.check_stock(free=10)

    # TEST 4: UNAUTHORIZED INSPECTION REQUEST

    def test_unauthorized_inspection_request(self):
        with self.assertRaises(ValidationError):
            self.request_inspection(actor=self.other_user)

        self.assertEqual(
            AssetInspection.objects.count(),
            0,
        )

    # TEST 5: CUSTODIAN ROLE REQUIRED

    def test_inspection_requires_custodian_role(self):
        self.custodian.groups.clear()

        with self.assertRaises(ValidationError):
            self.request_inspection()

    # TEST 6: SUPERUSER CAN REQUEST INSPECTION

    def test_superuser_can_request_inspection(self):
        inspection = self.request_inspection(
            actor=self.admin,
        )

        self.assertEqual(
            inspection.status,
            AssetInspection.Status.PENDING,
        )

    # TEST 7: INACTIVE USER REJECTED

    def test_inactive_user_cannot_request_inspection(self):
        self.custodian.is_active = False
        self.custodian.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            self.request_inspection()

    # TEST 8: ZERO INSPECTION QUANTITY

    def test_zero_inspection_quantity_rejected(self):
        with self.assertRaises(ValidationError):
            self.request_inspection(quantity=0)

    # TEST 9: EXCESSIVE INSPECTION QUANTITY

    def test_excessive_inspection_quantity_rejected(self):
        with self.assertRaises(ValidationError):
            self.request_inspection(quantity=11)

    # TEST 10: INVALID INSPECTION RECOMMENDATION

    def test_invalid_inspection_recommendation(self):
        inspection = self.request_inspection()

        with self.assertRaises(ValidationError):
            self.complete_inspection(
                inspection,
                recommendation="Invalid",
            )

        inspection.refresh_from_db()

        self.assertEqual(
            inspection.status,
            AssetInspection.Status.PENDING,
        )

    # TEST 11: CANNOT COMPLETE TWICE

    def test_cannot_complete_inspection_twice(self):
        inspection = self.request_inspection()
        self.complete_inspection(inspection)

        with self.assertRaises(ValidationError):
            self.complete_inspection(inspection)

    # TEST 12: CANNOT CANCEL COMPLETED INSPECTION

    def test_cannot_cancel_completed_inspection(self):
        inspection = self.request_inspection()
        self.complete_inspection(inspection)

        with self.assertRaises(ValidationError):
            cancel_asset_inspection(
                actor=self.custodian,
                inspection_id=inspection.pk,
            )

    # TEST 13: REQUEST DISPOSITION

    def test_request_disposition(self):
        disposition = self.prepare_disposition()

        self.assertEqual(
            disposition.status,
            AssetDisposition.Status.PENDING,
        )
        self.assertEqual(disposition.quantity, 2)

        self.check_stock(free=10)

    # TEST 14: MATCH INSPECTION RECOMMENDATION

    def test_disposition_must_match_recommendation(self):
        inspection = self.request_inspection()
        self.complete_inspection(
            inspection,
            recommendation=(
                AssetInspection.Recommendation.RECYCLE
            ),
        )

        with self.assertRaises(ValidationError):
            request_asset_disposition(
                actor=self.custodian,
                inspection_id=inspection.pk,
                disposition_type=(
                    AssetDisposition.DispositionType.DONATED
                ),
                reason="Incorrect disposition type",
            )

    # TEST 15: INCOMPLETE INSPECTION REJECTED

    def test_disposition_requires_completed_inspection(self):
        inspection = self.request_inspection()

        with self.assertRaises(ValidationError):
            request_asset_disposition(
                actor=self.custodian,
                inspection_id=inspection.pk,
                disposition_type=(
                    AssetDisposition.DispositionType.RECYCLED
                ),
                reason="Equipment requires recycling",
            )

    # TEST 16: REPAIR RECOMMENDATION NOT DISPOSITION

    def test_repair_recommendation_cannot_be_disposed(self):
        inspection = self.request_inspection()

        self.complete_inspection(
            inspection,
            recommendation=(
                AssetInspection.Recommendation.REPAIR
            ),
        )

        with self.assertRaises(ValidationError):
            request_asset_disposition(
                actor=self.custodian,
                inspection_id=inspection.pk,
                disposition_type=(
                    AssetDisposition.DispositionType.RECYCLED
                ),
                reason="Invalid action",
            )

    # TEST 17: DUPLICATE DISPOSITION REQUEST

    def test_duplicate_disposition_request_rejected(self):
        disposition = self.prepare_disposition()

        with self.assertRaises(ValidationError):
            request_asset_disposition(
                actor=self.custodian,
                inspection_id=disposition.inspection_id,
                disposition_type=disposition.disposition_type,
                reason="Duplicate disposition",
            )

    # TEST 18: EXECUTE PARTIAL LOT DISPOSITION

    def test_execute_partial_disposition(self):
        disposition = self.prepare_disposition(quantity=3)

        result = self.execute(disposition)

        self.assertEqual(
            result.status,
            AssetDisposition.Status.COMPLETED,
        )
        self.assertIsNotNone(result.completed_at)

        self.check_stock(free=7, retired=3)

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.lifecycle,
            Asset.Lifecycle.ACTIVE,
        )

    # TEST 19: EXECUTE FULL LOT DISPOSITION

    def test_execute_full_disposition(self):
        disposition = self.prepare_disposition(quantity=10)

        self.execute(disposition)

        self.check_stock(free=0, retired=10)

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.lifecycle,
            Asset.Lifecycle.RECYCLED,
        )
        self.assertEqual(
            self.asset.publication,
            Asset.Publication.WITHDRAWN,
        )

    # TEST 20: CANNOT EXECUTE TWICE

    def test_cannot_execute_disposition_twice(self):
        disposition = self.prepare_disposition(quantity=3)

        self.execute(disposition)

        with self.assertRaises(ValidationError):
            self.execute(disposition)

        self.check_stock(free=7, retired=3)

    # TEST 21: CANCEL PENDING DISPOSITION

    def test_cancel_pending_disposition(self):
        disposition = self.prepare_disposition()

        result = cancel_asset_disposition(
            actor=self.custodian,
            disposition_id=disposition.pk,
            reason="Disposition no longer required",
        )

        self.assertEqual(
            result.status,
            AssetDisposition.Status.CANCELLED,
        )

        self.assertIn(
            "Cancellation reason:",
            result.completion_notes,
        )

        self.check_stock(free=10)

    # TEST 22: CANNOT CANCEL COMPLETED DISPOSITION

    def test_cannot_cancel_completed_disposition(self):
        disposition = self.prepare_disposition()

        self.execute(disposition)

        with self.assertRaises(ValidationError):
            cancel_asset_disposition(
                actor=self.custodian,
                disposition_id=disposition.pk,
                reason="Attempted cancellation",
            )

        self.check_stock(free=8, retired=2)

    # TEST 23: UNAUTHORIZED EXECUTION REJECTED

    def test_unauthorized_user_cannot_execute(self):
        disposition = self.prepare_disposition()

        with self.assertRaises(ValidationError):
            self.execute(
                disposition,
                actor=self.other_user,
            )

        self.check_stock(free=10)

    # TEST 24: PRESERVE HELD STOCK

    def test_disposition_preserves_held_stock(self):
        stock = self.asset.stock

        stock.free = 7
        stock.held = 3
        stock.full_clean()
        stock.save()

        disposition = self.prepare_disposition(quantity=2)

        self.execute(disposition)

        self.check_stock(
            free=5,
            retired=2,
            held=3,
        )

    # TEST 25: PRESERVE IN-TRANSIT STOCK

    def test_disposition_preserves_in_transit_stock(self):
        stock = self.asset.stock

        stock.free = 6
        stock.in_transit = 4
        stock.full_clean()
        stock.save()

        disposition = self.prepare_disposition(quantity=3)

        self.execute(disposition)

        self.check_stock(
            free=3,
            retired=3,
            in_transit=4,
        )

    # TEST 26: INSUFFICIENT FREE STOCK

    def test_insufficient_free_stock_prevents_execution(self):
        disposition = self.prepare_disposition(quantity=4)

        stock = self.asset.stock
        stock.free = 2
        stock.held = 8
        stock.full_clean()
        stock.save()

        with self.assertRaises(ValidationError):
            self.execute(disposition)

        disposition.refresh_from_db()

        self.assertEqual(
            disposition.status,
            AssetDisposition.Status.PENDING,
        )

        self.check_stock(free=2, held=8)

    # TEST 27: PROTECT MAINTENANCE-BLOCKED STOCK

    def test_disposition_preserves_maintenance_stock(self):
        report_asset_maintenance(
            actor=self.custodian,
            asset_id=self.asset.pk,
            title="Laptop repairs",
            description="Four units require repair",
            quantity=4,
        )

        disposition = self.prepare_disposition(quantity=3)

        self.execute(disposition)

        self.check_stock(
            free=3,
            retired=3,
            blocked=4,
        )

    # TEST 28: MULTIPLE PARTIAL DISPOSITIONS

    def test_multiple_partial_dispositions(self):
        first = self.prepare_disposition(
            quantity=3,
            recommendation=(
                AssetInspection.Recommendation.RECYCLE
            ),
            disposition_type=(
                AssetDisposition.DispositionType.RECYCLED
            ),
        )

        second = self.prepare_disposition(
            quantity=2,
            recommendation=(
                AssetInspection.Recommendation.DONATE
            ),
            disposition_type=(
                AssetDisposition.DispositionType.DONATED
            ),
        )

        self.execute(first)
        self.execute(second)

        self.check_stock(free=5, retired=5)

        self.asset.refresh_from_db()

        self.assertEqual(
            self.asset.lifecycle,
            Asset.Lifecycle.ACTIVE,
        )

        self.assertEqual(
            AssetDisposition.objects.filter(
                status=AssetDisposition.Status.COMPLETED
            ).count(),
            2,
        )

    # TEST 29: FAILED DATABASE SAVE ROLLS BACK STOCK

    def test_failed_disposition_save_rolls_back_stock(self):
        disposition = self.prepare_disposition(quantity=3)

        original_save = AssetDisposition.save

        def failing_save(instance, *args, **kwargs):
            original_save(instance, *args, **kwargs)

            raise RuntimeError(
                "Simulated disposition save failure"
            )

        with patch.object(
            AssetDisposition,
            "save",
            failing_save,
        ):
            with self.assertRaises(RuntimeError):
                self.execute(disposition)

        disposition.refresh_from_db()

        self.assertEqual(
            disposition.status,
            AssetDisposition.Status.PENDING,
        )

        self.check_stock(free=10, retired=0)

    # TEST 30: FULL DISPOSITION AFTER PARTIAL OPERATIONS

    def test_final_disposition_with_mixed_history(self):
        first = self.prepare_disposition(
            quantity=4,
            recommendation=(
                AssetInspection.Recommendation.RECYCLE
            ),
            disposition_type=(
                AssetDisposition.DispositionType.RECYCLED
            ),
        )

        self.execute(first)

        self.check_stock(free=6, retired=4)

        second = self.prepare_disposition(
            quantity=6,
            recommendation=(
                AssetInspection.Recommendation.DONATE
            ),
            disposition_type=(
                AssetDisposition.DispositionType.DONATED
            ),
        )

        self.execute(second)

        self.check_stock(free=0, retired=10)

        self.asset.refresh_from_db()

        # Current implementation sets the asset-wide
        # lifecycle to the final disposition type.
        self.assertEqual(
            self.asset.lifecycle,
            Asset.Lifecycle.DONATED,
        )

        self.assertEqual(
            self.asset.publication,
            Asset.Publication.WITHDRAWN,
        )

        # Historical dispositions retain their
        # individual recorded types and quantities.
        self.assertEqual(
            AssetDisposition.objects.filter(
                asset=self.asset,
                status=AssetDisposition.Status.COMPLETED,
            ).count(),
            2,
        )
