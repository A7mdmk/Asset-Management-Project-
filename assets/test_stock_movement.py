
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import DepartmentApprover

from workflows.models import RequestApproval
from workflows.services import (
    submit_request,
    decide_request,
    cancel_approved_reservation,
    arrange_transfer,
    dispatch_transfer,
    confirm_transfer_receipt,
    cancel_arranged_transfer,
)

from .models import (
    Asset,
    AssetInspection,
    AssetDisposition,
    Category,
    Department,
    StockMovement,
)

from .services import (
    register_asset,
    record_stock_movement,
    report_asset_maintenance,
    start_asset_repair,
    complete_asset_repair,
    cancel_asset_maintenance,
    request_asset_inspection,
    complete_asset_inspection,
    request_asset_disposition,
    execute_asset_disposition,
)


class StockMovementHistoryTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.department = Department.objects.create(
            name="Stock History Department",
            code="STOCK-HIST",
        )

        self.destination = Department.objects.create(
            name="Stock History Destination",
            code="STOCK-DEST",
        )

        self.category = Category.objects.create(
            name="Stock History Equipment",
        )

        self.custodian = User.objects.create_user(
            username="stock_history_custodian",
            password="TestPassword123!",
        )

        self.requester = User.objects.create_user(
            username="stock_history_requester",
            password="TestPassword123!",
        )

        self.approver = User.objects.create_user(
            username="stock_history_approver",
            password="TestPassword123!",
        )

        custodian_group, _ = Group.objects.get_or_create(
            name="Custodian"
        )
        requester_group, _ = Group.objects.get_or_create(
            name="Requester"
        )
        approver_group, _ = Group.objects.get_or_create(
            name="Approver/Admin"
        )

        self.custodian.groups.add(custodian_group)
        self.requester.groups.add(requester_group)
        self.approver.groups.add(approver_group)

        DepartmentApprover.objects.create(
            department=self.destination,
            user=self.approver,
            is_active=True,
        )

        self.asset = register_asset(
            name="Stock History Laptops",
            asset_tag="STOCK-HIST-001",
            category=self.category,
            department=self.department,
            custodian=self.custodian,
            location="Engineering Lab",
            tracking_mode=Asset.TrackingMode.LOT,
            quantity=10,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.PUBLISHED,
        )

    def movements(self, movement_type=None):
        records = StockMovement.objects.filter(
            asset=self.asset
        )
        if movement_type:
            records = records.filter(
                movement_type=movement_type
            )
        return records

    def assert_movement(
        self,
        movement_type,
        source,
        destination,
        quantity,
    ):
        records = self.movements(movement_type)

        self.assertEqual(records.count(), 1)

        movement = records.get()

        self.assertEqual(movement.source, source)
        self.assertEqual(
            movement.destination,
            destination,
        )
        self.assertEqual(movement.quantity, quantity)

        return movement

    def submit(self, quantity=2):
        return submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.destination.pk,
            quantity=quantity,
            reason="Equipment needed for a project",
        )

    def approve(self, quantity=2):
        request = self.submit(quantity)

        decide_request(
            approver=self.approver,
            request_id=request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        decide_request(
            approver=self.custodian,
            request_id=request.pk,
            stage=RequestApproval.Stage.SOURCE,
            decision=RequestApproval.Decision.APPROVED,
        )

        return request.reservation

    def arrange(self, quantity=2):
        reservation = self.approve(quantity)

        return arrange_transfer(
            actor=self.custodian,
            reservation_id=reservation.pk,
        )

    def report_maintenance(self, quantity=2):
        return report_asset_maintenance(
            actor=self.custodian,
            asset_id=self.asset.pk,
            title="Equipment repair",
            description="Equipment requires maintenance",
            quantity=quantity,
        )

    def prepare_disposition(self, quantity=2):
        inspection = request_asset_inspection(
            actor=self.custodian,
            asset_id=self.asset.pk,
            quantity=quantity,
        )

        complete_asset_inspection(
            actor=self.custodian,
            inspection_id=inspection.pk,
            findings="Equipment no longer suitable",
            recommendation=(
                AssetInspection.Recommendation.RECYCLE
            ),
        )

        return request_asset_disposition(
            actor=self.custodian,
            inspection_id=inspection.pk,
            disposition_type=(
                AssetDisposition.DispositionType.RECYCLED
            ),
            reason="Equipment should be recycled",
        )

    # TEST 1
    def test_registration_creates_movement(self):
        movement = self.assert_movement(
            StockMovement.MovementType.REGISTRATION,
            "",
            StockMovement.Bucket.FREE,
            10,
        )

        self.assertIsNone(movement.performed_by)
        self.assertIsNotNone(movement.created_at)

    # TEST 2
    def test_unsafe_registration_is_blocked(self):
        asset = register_asset(
            name="Unsafe Equipment",
            category=self.category,
            department=self.department,
            custodian=self.custodian,
            location="Storage",
            tracking_mode=Asset.TrackingMode.LOT,
            quantity=3,
            condition=Asset.Condition.UNSAFE,
        )

        movement = StockMovement.objects.get(
            asset=asset
        )

        self.assertEqual(
            movement.destination,
            StockMovement.Bucket.BLOCKED,
        )
        self.assertEqual(movement.quantity, 3)
        self.assertEqual(asset.stock.blocked, 3)

    # TEST 3
    def test_invalid_movement_is_rejected(self):
        with self.assertRaises(ValidationError):
            record_stock_movement(
                asset=self.asset,
                movement_type=(
                    StockMovement.MovementType.DISPATCH
                ),
                quantity=2,
                source=StockMovement.Bucket.FREE,
                destination=StockMovement.Bucket.FREE,
                actor=self.custodian,
            )

        self.assertEqual(self.movements().count(), 1)

    # TEST 4
    def test_registration_logging_failure_rolls_back(self):
        with patch(
            "assets.services.record_stock_movement",
            side_effect=RuntimeError("Audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                register_asset(
                    name="Failed Registration",
                    category=self.category,
                    department=self.department,
                    custodian=self.custodian,
                    location="Storage",
                    tracking_mode=Asset.TrackingMode.LOT,
                    quantity=2,
                )

        self.assertFalse(
            Asset.objects.filter(
                name="Failed Registration"
            ).exists()
        )

    # TEST 5
    def test_maintenance_report_movement(self):
        maintenance = self.report_maintenance()

        movement = self.assert_movement(
            StockMovement.MovementType.MAINTENANCE_REPORT,
            StockMovement.Bucket.FREE,
            StockMovement.Bucket.BLOCKED,
            2,
        )

        self.assertEqual(
            movement.reference_id,
            str(maintenance.pk),
        )
        self.assertEqual(
            movement.performed_by,
            self.custodian,
        )

    # TEST 6
    def test_successful_repair_movement(self):
        maintenance = self.report_maintenance()

        start_asset_repair(
            actor=self.custodian,
            maintenance_id=maintenance.pk,
        )

        complete_asset_repair(
            actor=self.custodian,
            maintenance_id=maintenance.pk,
            repair_notes="Repair successful",
            return_to_service=True,
        )

        self.assert_movement(
            StockMovement.MovementType.REPAIR_COMPLETE,
            StockMovement.Bucket.BLOCKED,
            StockMovement.Bucket.FREE,
            2,
        )

        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 10)

    # TEST 7
    def test_unsuccessful_repair_has_no_release_movement(self):
        maintenance = self.report_maintenance()

        start_asset_repair(
            actor=self.custodian,
            maintenance_id=maintenance.pk,
        )

        complete_asset_repair(
            actor=self.custodian,
            maintenance_id=maintenance.pk,
            repair_notes="Repair unsuccessful",
            return_to_service=False,
        )

        self.assertFalse(
            self.movements(
                StockMovement.MovementType.REPAIR_COMPLETE
            ).exists()
        )

        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.blocked, 2)

    # TEST 8
    def test_maintenance_cancellation_movement(self):
        maintenance = self.report_maintenance()

        cancel_asset_maintenance(
            actor=self.custodian,
            maintenance_id=maintenance.pk,
            reason="No repair required",
        )

        self.assert_movement(
            StockMovement.MovementType.MAINTENANCE_CANCEL,
            StockMovement.Bucket.BLOCKED,
            StockMovement.Bucket.FREE,
            2,
        )

    # TEST 9
    def test_disposition_movement(self):
        disposition = self.prepare_disposition(3)

        execute_asset_disposition(
            actor=self.custodian,
            disposition_id=disposition.pk,
            completion_notes="Recycling completed",
        )

        movement = self.assert_movement(
            StockMovement.MovementType.DISPOSITION,
            StockMovement.Bucket.FREE,
            StockMovement.Bucket.RETIRED,
            3,
        )

        self.assertEqual(
            movement.reference_id,
            str(disposition.pk),
        )

    # TEST 10
    def test_inspection_and_disposition_requests_do_not_move_stock(self):
        self.prepare_disposition()

        self.assertEqual(self.movements().count(), 1)

    # TEST 11
    def test_request_submission_does_not_move_stock(self):
        self.submit()

        self.assertEqual(self.movements().count(), 1)

    # TEST 12
    def test_source_approval_creates_reservation_movement(self):
        reservation = self.approve()

        movement = self.assert_movement(
            StockMovement.MovementType.RESERVATION,
            StockMovement.Bucket.FREE,
            StockMovement.Bucket.HELD,
            2,
        )

        self.assertEqual(
            movement.reference_id,
            str(reservation.pk),
        )
        self.assertEqual(
            movement.performed_by,
            self.custodian,
        )

    # TEST 13
    def test_destination_approval_does_not_move_stock(self):
        request = self.submit()

        decide_request(
            approver=self.approver,
            request_id=request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        self.assertEqual(self.movements().count(), 1)

    # TEST 14
    def test_reservation_cancellation_returns_free_stock(self):
        reservation = self.approve()

        cancel_approved_reservation(
            actor=self.requester,
            reservation_id=reservation.pk,
            reason="Equipment no longer needed",
        )

        self.assert_movement(
            StockMovement.MovementType.RESERVATION_CANCEL,
            StockMovement.Bucket.HELD,
            StockMovement.Bucket.FREE,
            2,
        )

    # TEST 15
    def test_unsafe_reservation_cancellation_blocks_stock(self):
        reservation = self.approve()

        self.asset.condition = Asset.Condition.UNSAFE
        self.asset.save(update_fields=["condition"])

        cancel_approved_reservation(
            actor=self.requester,
            reservation_id=reservation.pk,
            reason="Equipment became unsafe",
        )

        self.assert_movement(
            StockMovement.MovementType.RESERVATION_CANCEL,
            StockMovement.Bucket.HELD,
            StockMovement.Bucket.BLOCKED,
            2,
        )

    # TEST 16
    def test_dispatch_creates_movement(self):
        transfer = self.arrange()

        dispatch_transfer(
            actor=self.custodian,
            transfer_id=transfer.pk,
        )

        self.assert_movement(
            StockMovement.MovementType.DISPATCH,
            StockMovement.Bucket.HELD,
            StockMovement.Bucket.IN_TRANSIT,
            2,
        )

    # TEST 17
    def test_receipt_creates_movement(self):
        transfer = self.arrange()

        dispatch_transfer(
            actor=self.custodian,
            transfer_id=transfer.pk,
        )

        confirm_transfer_receipt(
            actor=self.approver,
            transfer_id=transfer.pk,
        )

        self.assert_movement(
            StockMovement.MovementType.RECEIPT,
            StockMovement.Bucket.IN_TRANSIT,
            StockMovement.Bucket.IN_USE,
            2,
        )

    # TEST 18
    def test_transfer_cancellation_creates_movement(self):
        transfer = self.arrange()

        cancel_arranged_transfer(
            actor=self.custodian,
            transfer_id=transfer.pk,
            reason="Transfer cancelled",
        )

        self.assert_movement(
            StockMovement.MovementType.TRANSFER_CANCEL,
            StockMovement.Bucket.HELD,
            StockMovement.Bucket.FREE,
            2,
        )

    # TEST 19
    def test_duplicate_dispatch_does_not_duplicate_movement(self):
        transfer = self.arrange()

        dispatch_transfer(
            actor=self.custodian,
            transfer_id=transfer.pk,
        )

        with self.assertRaises(ValidationError):
            dispatch_transfer(
                actor=self.custodian,
                transfer_id=transfer.pk,
            )

        self.assertEqual(
            self.movements(
                StockMovement.MovementType.DISPATCH
            ).count(),
            1,
        )

    # TEST 20
    def test_audit_failure_rolls_back_dispatch(self):
        transfer = self.arrange()

        with patch(
            "workflows.services.record_stock_movement",
            side_effect=RuntimeError("Audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                dispatch_transfer(
                    actor=self.custodian,
                    transfer_id=transfer.pk,
                )

        transfer.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            transfer.status,
            "Arranged",
        )
        self.assertEqual(self.asset.stock.held, 2)
        self.assertEqual(self.asset.stock.in_transit, 0)

        self.assertFalse(
            self.movements(
                StockMovement.MovementType.DISPATCH
            ).exists()
        )
