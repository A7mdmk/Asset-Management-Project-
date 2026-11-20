
from unittest.mock import patch
from workflows.services import submit_request
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import (
    Asset,
    AssetMaintenance,
    Category,
    Department,
    StockBalance,
)

from .services import (
    register_asset,
    report_asset_maintenance,
    start_asset_repair,
    complete_asset_repair,
    cancel_asset_maintenance,
)


class AssetMaintenanceTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.department = Department.objects.create(
            name="Maintenance Test Department",
            code="MAINT-TEST",
        )

        self.category = Category.objects.create(
            name="Maintenance Test Equipment",
        )

        self.custodian = User.objects.create_user(
            username="maintenance_custodian",
            password="TestPassword123!",
        )

        self.other_user = User.objects.create_user(
            username="maintenance_other",
            password="TestPassword123!",
        )

        self.superuser = User.objects.create_superuser(
            username="maintenance_admin",
            email="maintenance_admin@example.com",
            password="TestPassword123!",
        )

        group, _ = Group.objects.get_or_create(
            name="Custodian",
        )
        self.custodian.groups.add(group)

        self.asset = register_asset(
            name="Maintenance Test Laptops",
            asset_tag="MAINT-001",
            description="Laptop equipment for testing",
            category=self.category,
            department=self.department,
            custodian=self.custodian,
            location="CS Lab",
            tracking_mode=Asset.TrackingMode.LOT,
            quantity=10,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.PUBLISHED,
        )

    def report(self, quantity=2, actor=None):
        return report_asset_maintenance(
            actor=actor or self.custodian,
            asset_id=self.asset.pk,
            title="Laptop Repair",
            description="Equipment requires maintenance",
            quantity=quantity,
        )

    def start(self, maintenance, actor=None):
        return start_asset_repair(
            actor=actor or self.custodian,
            maintenance_id=maintenance.pk,
        )

    def complete(
        self,
        maintenance,
        return_to_service=True,
        actor=None,
    ):
        return complete_asset_repair(
            actor=actor or self.custodian,
            maintenance_id=maintenance.pk,
            repair_notes="Repair work completed",
            return_to_service=return_to_service,
        )

    def cancel(self, maintenance, actor=None):
        return cancel_asset_maintenance(
            actor=actor or self.custodian,
            maintenance_id=maintenance.pk,
            reason="Maintenance no longer required",
        )

    def check_stock(
        self,
        *,
        free,
        blocked,
        held=0,
        in_transit=0,
        in_use=0,
    ):
        stock = StockBalance.objects.get(asset=self.asset)

        self.assertEqual(stock.free, free)
        self.assertEqual(stock.blocked, blocked)
        self.assertEqual(stock.held, held)
        self.assertEqual(stock.in_transit, in_transit)
        self.assertEqual(stock.in_use, in_use)
        self.assertEqual(stock.total, 10)

    # TEST 1: REPORT MAINTENANCE

    def test_report_maintenance(self):
        maintenance = self.report()

        self.assertEqual(
            maintenance.status,
            AssetMaintenance.Status.REPORTED,
        )
        self.assertEqual(maintenance.quantity, 2)

        self.check_stock(free=8, blocked=2)

    # TEST 2: START REPAIR

    def test_start_repair(self):
        maintenance = self.report()

        result = self.start(maintenance)

        self.assertEqual(
            result.status,
            AssetMaintenance.Status.IN_PROGRESS,
        )
        self.assertIsNotNone(result.started_at)

        self.check_stock(free=8, blocked=2)

    # TEST 3: SUCCESSFUL REPAIR

    def test_complete_successful_repair(self):
        maintenance = self.report()
        self.start(maintenance)

        result = self.complete(
            maintenance,
            return_to_service=True,
        )

        self.assertEqual(
            result.status,
            AssetMaintenance.Status.COMPLETED,
        )
        self.assertIsNotNone(result.completed_at)

        self.check_stock(free=10, blocked=0)

    # TEST 4: UNSUCCESSFUL REPAIR

    def test_complete_unsuccessful_repair(self):
        maintenance = self.report()
        self.start(maintenance)

        result = self.complete(
            maintenance,
            return_to_service=False,
        )

        self.assertEqual(
            result.status,
            AssetMaintenance.Status.COMPLETED,
        )

        self.check_stock(free=8, blocked=2)

    # TEST 5: CANCEL REPORTED MAINTENANCE

    def test_cancel_reported_maintenance(self):
        maintenance = self.report()

        result = self.cancel(maintenance)

        self.assertEqual(
            result.status,
            AssetMaintenance.Status.CANCELLED,
        )

        self.assertIn(
            "Cancellation reason:",
            result.repair_notes,
        )

        self.check_stock(free=10, blocked=0)

    # TEST 6: UNAUTHORIZED REPORT

    def test_unauthorized_user_cannot_report(self):
        with self.assertRaises(ValidationError):
            self.report(actor=self.other_user)

        self.assertEqual(
            AssetMaintenance.objects.count(),
            0,
        )

        self.check_stock(free=10, blocked=0)

    # TEST 7: CUSTODIAN ROLE REQUIRED

    def test_custodian_role_required(self):
        self.custodian.groups.clear()

        with self.assertRaises(ValidationError):
            self.report()

        self.check_stock(free=10, blocked=0)

    # TEST 8: SUPERUSER CAN REPORT

    def test_superuser_can_report(self):
        maintenance = self.report(
            actor=self.superuser
        )

        self.assertEqual(
            maintenance.status,
            AssetMaintenance.Status.REPORTED,
        )

        self.check_stock(free=8, blocked=2)

    # TEST 9: INACTIVE USER REJECTED

    def test_inactive_user_cannot_report(self):
        self.custodian.is_active = False
        self.custodian.save(
            update_fields=["is_active"]
        )

        with self.assertRaises(ValidationError):
            self.report()

        self.check_stock(free=10, blocked=0)

    # TEST 10: INVALID ZERO QUANTITY

    def test_zero_quantity_rejected(self):
        with self.assertRaises(ValidationError):
            self.report(quantity=0)

        self.check_stock(free=10, blocked=0)

    # TEST 11: INVALID NEGATIVE QUANTITY

    def test_negative_quantity_rejected(self):
        with self.assertRaises(ValidationError):
            self.report(quantity=-1)

        self.check_stock(free=10, blocked=0)

    # TEST 12: EXCESSIVE QUANTITY

    def test_insufficient_free_stock_rejected(self):
        with self.assertRaises(ValidationError):
            self.report(quantity=11)

        self.check_stock(free=10, blocked=0)

    # TEST 13: DUPLICATE START REJECTED

    def test_cannot_start_repair_twice(self):
        maintenance = self.report()
        self.start(maintenance)

        with self.assertRaises(ValidationError):
            self.start(maintenance)

        self.check_stock(free=8, blocked=2)

    # TEST 14: COMPLETE BEFORE START REJECTED

    def test_cannot_complete_reported_repair(self):
        maintenance = self.report()

        with self.assertRaises(ValidationError):
            self.complete(maintenance)

        self.check_stock(free=8, blocked=2)

    # TEST 15: DUPLICATE COMPLETION REJECTED

    def test_cannot_complete_repair_twice(self):
        maintenance = self.report()
        self.start(maintenance)
        self.complete(maintenance)

        with self.assertRaises(ValidationError):
            self.complete(maintenance)

        self.check_stock(free=10, blocked=0)

    # TEST 16: CANNOT CANCEL ACTIVE REPAIR

    def test_cannot_cancel_in_progress_repair(self):
        maintenance = self.report()
        self.start(maintenance)

        with self.assertRaises(ValidationError):
            self.cancel(maintenance)

        self.check_stock(free=8, blocked=2)

    # TEST 17: DUPLICATE CANCELLATION

    def test_cannot_cancel_twice(self):
        maintenance = self.report()
        self.cancel(maintenance)

        with self.assertRaises(ValidationError):
            self.cancel(maintenance)

        self.check_stock(free=10, blocked=0)

    # TEST 18: UNSAFE ASSET CANNOT RETURN TO SERVICE

    def test_unsafe_asset_cannot_return_to_service(self):
        maintenance = self.report()
        self.start(maintenance)

        self.asset.condition = Asset.Condition.UNSAFE
        self.asset.save(update_fields=["condition"])

        with self.assertRaises(ValidationError):
            self.complete(
                maintenance,
                return_to_service=True,
            )

        maintenance.refresh_from_db()

        self.assertEqual(
            maintenance.status,
            AssetMaintenance.Status.IN_PROGRESS,
        )

        self.check_stock(free=8, blocked=2)

    # TEST 19: UNSAFE ASSET CANNOT BE RELEASED
    # THROUGH CANCELLATION

    def test_unsafe_asset_cannot_cancel_maintenance(self):
        maintenance = self.report()

        self.asset.condition = Asset.Condition.UNSAFE
        self.asset.save(update_fields=["condition"])

        with self.assertRaises(ValidationError):
            self.cancel(maintenance)

        self.check_stock(free=8, blocked=2)

    # TEST 20: MULTIPLE MAINTENANCE RECORDS

    def test_multiple_maintenance_records(self):
        first = self.report(quantity=2)
        second = self.report(quantity=3)

        self.check_stock(free=5, blocked=5)

        self.start(first)
        self.complete(first)

        self.check_stock(free=7, blocked=3)

        self.start(second)
        self.complete(second)

        self.check_stock(free=10, blocked=0)

    # TEST 21: PARTIAL REPAIR AVAILABILITY

    def test_only_repaired_quantity_returns_to_free(self):
        first = self.report(quantity=2)
        self.report(quantity=3)

        self.start(first)
        self.complete(first)

        self.check_stock(free=7, blocked=3)

    # TEST 22: HELD STOCK IS PRESERVED

    def test_maintenance_does_not_change_held_stock(self):
        stock = self.asset.stock
        stock.free = 6
        stock.held = 4
        stock.full_clean()
        stock.save()

        maintenance = self.report(quantity=2)

        self.check_stock(
            free=4,
            blocked=2,
            held=4,
        )

        self.start(maintenance)
        self.complete(maintenance)

        self.check_stock(
            free=6,
            blocked=0,
            held=4,
        )

    # TEST 23: INVALID COMPLETION NOTES

    def test_completion_requires_repair_notes(self):
        maintenance = self.report()
        self.start(maintenance)

        with self.assertRaises(ValidationError):
            complete_asset_repair(
                actor=self.custodian,
                maintenance_id=maintenance.pk,
                repair_notes="   ",
                return_to_service=True,
            )

        self.check_stock(free=8, blocked=2)

    # TEST 24: UNAUTHORIZED COMPLETION

    def test_unauthorized_user_cannot_complete(self):
        maintenance = self.report()
        self.start(maintenance)

        with self.assertRaises(ValidationError):
            self.complete(
                maintenance,
                actor=self.other_user,
            )

        maintenance.refresh_from_db()

        self.assertEqual(
            maintenance.status,
            AssetMaintenance.Status.IN_PROGRESS,
        )

        self.check_stock(free=8, blocked=2)

    # TEST 25: DATABASE FAILURE ROLLS BACK STOCK

    def test_failed_maintenance_save_rolls_back_stock(self):
        original_save = AssetMaintenance.save

        def failing_save(instance, *args, **kwargs):
            original_save(instance, *args, **kwargs)

            raise RuntimeError(
                "Simulated maintenance save failure"
            )

        with patch.object(
            AssetMaintenance,
            "save",
            failing_save,
        ):
            with self.assertRaises(RuntimeError):
                self.report()

        self.assertEqual(
            AssetMaintenance.objects.count(),
            0,
        )

        self.check_stock(free=10, blocked=0)

    # TEST 26: PRESERVE STOCK BLOCKED FOR OTHER REASONS

    def test_other_blocked_stock_remains_blocked(self):
        stock = self.asset.stock

        stock.free = 8
        stock.blocked = 2
        stock.full_clean()
        stock.save()

        maintenance = self.report(quantity=3)

        self.check_stock(free=5, blocked=5)

        self.start(maintenance)
        self.complete(maintenance)

        # The original 2 blocked units must remain blocked.
        self.check_stock(free=8, blocked=2)

    # TEST 27: PRESERVE HELD AND IN-TRANSIT STOCK

    def test_maintenance_preserves_transfer_stock(self):
        stock = self.asset.stock

        stock.free = 5
        stock.held = 2
        stock.in_transit = 3
        stock.full_clean()
        stock.save()

        maintenance = self.report(quantity=2)

        self.check_stock(
            free=3,
            blocked=2,
            held=2,
            in_transit=3,
        )

        self.start(maintenance)
        self.complete(maintenance)

        self.check_stock(
            free=5,
            blocked=0,
            held=2,
            in_transit=3,
        )

    # TEST 28: DETECT INSUFFICIENT MAINTENANCE STOCK

    def test_start_rejects_inconsistent_blocked_stock(self):
        maintenance = self.report(quantity=3)

        stock = self.asset.stock
        stock.blocked = 2
        stock.free = 8
        stock.full_clean()
        stock.save()

        with self.assertRaises(ValidationError):
            self.start(maintenance)

        maintenance.refresh_from_db()

        self.assertEqual(
            maintenance.status,
            AssetMaintenance.Status.REPORTED,
        )

        self.check_stock(free=8, blocked=2)

    # TEST 29: COMPLETION CANNOT CONSUME
    # ANOTHER MAINTENANCE RECORD'S STOCK

    def test_completion_preserves_other_maintenance(self):
        first = self.report(quantity=2)
        second = self.report(quantity=3)

        self.start(first)

        # Simulate an inconsistent external stock update.
        stock = self.asset.stock
        stock.free = 7
        stock.blocked = 3
        stock.full_clean()
        stock.save()

        with self.assertRaises(ValidationError):
            self.complete(first)

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertEqual(
            first.status,
            AssetMaintenance.Status.IN_PROGRESS,
        )

        self.assertEqual(
            second.status,
            AssetMaintenance.Status.REPORTED,
        )

        # The failed operation must roll back.
        self.check_stock(free=7, blocked=3)

    # TEST 30: CANCELLATION CANNOT CONSUME
    # ANOTHER MAINTENANCE RECORD'S STOCK

    def test_cancellation_preserves_other_maintenance(self):
        first = self.report(quantity=2)
        second = self.report(quantity=3)

        stock = self.asset.stock
        stock.free = 7
        stock.blocked = 3
        stock.full_clean()
        stock.save()

        with self.assertRaises(ValidationError):
            self.cancel(first)

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertEqual(
            first.status,
            AssetMaintenance.Status.REPORTED,
        )

        self.assertEqual(
            second.status,
            AssetMaintenance.Status.REPORTED,
        )

        self.check_stock(free=7, blocked=3)

    # TEST 31: REPORTING ROLLS BACK
    # WHEN EXISTING MAINTENANCE IS UNDERFUNDED

    def test_reporting_rolls_back_on_integrity_failure(self):
        existing = self.report(quantity=3)

        stock = self.asset.stock
        stock.free = 8
        stock.blocked = 2
        stock.full_clean()
        stock.save()

        with self.assertRaises(ValidationError):
            self.report(quantity=1)

        self.assertEqual(
            AssetMaintenance.objects.count(),
            1,
        )

        existing.refresh_from_db()

        self.assertEqual(
            existing.status,
            AssetMaintenance.Status.REPORTED,
        )

        self.check_stock(free=8, blocked=2)

    # TEST 32: EXISTING RESOURCE REQUEST WORKFLOW
    # RESPECTS MAINTENANCE-BLOCKED STOCK

    def test_resource_requests_respect_maintenance_stock(self):
        requester = get_user_model().objects.create_user(
            username="maintenance_requester",
            password="TestPassword123!",
        )

        requester_group, _ = Group.objects.get_or_create(
            name="Requester",
        )
        requester.groups.add(requester_group)

        destination = Department.objects.create(
            name="Maintenance Destination",
            code="MAINT-DEST",
        )

        # Nine units become unavailable for requests.
        self.report(quantity=9)

        self.check_stock(free=1, blocked=9)

        with self.assertRaises(ValidationError):
            submit_request(
                requester=requester,
                asset_id=self.asset.pk,
                destination_department_id=destination.pk,
                quantity=2,
                reason="Need laptops for a project",
            )

        # One unit remains free and can be requested.
        request = submit_request(
            requester=requester,
            asset_id=self.asset.pk,
            destination_department_id=destination.pk,
            quantity=1,
            reason="Need one laptop for a project",
        )

        self.assertEqual(request.quantity, 1)

        # Submission must not move stock;
        # reservation occurs at final approval.
        self.check_stock(free=1, blocked=9)
