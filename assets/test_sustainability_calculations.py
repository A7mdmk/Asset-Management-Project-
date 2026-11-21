
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from assets.models import (
    Asset,
    AssetMaintenance,
    AssetInspection,
    AssetDisposition,
    Category,
    Department,
)
from assets.services import register_asset
from assets.sustainability_services import (
    get_sustainability_summary,
)

from workflows.models import (
    ResourceRequest,
    RequestApproval,
    Reservation,
    Transfer,
)


User = get_user_model()


class SustainabilityCalculationTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="sustainability_metrics_user",
            password="TestPassword123!",
        )

        self.custodian = User.objects.create_user(
            username="sustainability_metrics_custodian",
            password="TestPassword123!",
        )

        self.department = Department.objects.create(
            name="Sustainability Engineering",
            code="SUSENG",
        )

        self.category = Category.objects.create(
            name="Sustainability Equipment",
        )

        self.asset = register_asset(
            name="Sustainability Test Laptop",
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

    def test_registered_assets_count(self):
        summary = get_sustainability_summary()

        self.assertEqual(
            summary["total_registered_assets"],
            1,
        )

        self.assertEqual(
            summary["available_units"],
            10,
        )

    def test_available_units_follow_stock_balance(self):
        stock = self.asset.stock

        stock.free = 6
        stock.held = 4
        stock.full_clean()
        stock.save()

        summary = get_sustainability_summary()

        self.assertEqual(
            summary["available_units"],
            6,
        )

    def test_only_completed_repairs_are_counted(self):
        AssetMaintenance.objects.create(
            asset=self.asset,
            reported_by=self.user,
            title="Completed laptop repair",
            description="Repair completed successfully.",
            quantity=3,
            status=AssetMaintenance.Status.COMPLETED,
            completed_at=timezone.now(),
        )

        AssetMaintenance.objects.create(
            asset=self.asset,
            reported_by=self.user,
            title="Pending laptop repair",
            description="Waiting for repair.",
            quantity=2,
            status=AssetMaintenance.Status.REPORTED,
        )

        summary = get_sustainability_summary()

        self.assertEqual(
            summary["repaired_units"],
            3,
        )

    def create_completed_inspection(self):
        return AssetInspection.objects.create(
            asset=self.asset,
            requested_by=self.user,
            inspected_by=self.custodian,
            quantity=5,
            status=AssetInspection.Status.COMPLETED,
            findings="Inspection completed.",
            recommendation=AssetInspection.Recommendation.RECYCLE,
            inspected_at=timezone.now(),
        )

    def test_completed_donations_are_counted(self):
        inspection = self.create_completed_inspection()

        AssetDisposition.objects.create(
            asset=self.asset,
            inspection=inspection,
            requested_by=self.user,
            completed_by=self.custodian,
            disposition_type=(
                AssetDisposition.DispositionType.DONATED
            ),
            quantity=2,
            status=AssetDisposition.Status.COMPLETED,
            reason="Donation to another organization.",
            completed_at=timezone.now(),
        )

        summary = get_sustainability_summary()

        self.assertEqual(
            summary["donated_units"],
            2,
        )

        self.assertEqual(
            summary["recycled_units"],
            0,
        )

    def test_pending_recycling_is_not_counted(self):
        inspection = self.create_completed_inspection()

        AssetDisposition.objects.create(
            asset=self.asset,
            inspection=inspection,
            requested_by=self.user,
            disposition_type=(
                AssetDisposition.DispositionType.RECYCLED
            ),
            quantity=2,
            status=AssetDisposition.Status.PENDING,
            reason="Pending recycling approval.",
        )

        summary = get_sustainability_summary()

        self.assertEqual(
            summary["recycled_units"],
            0,
        )

    def test_only_received_transfers_count_as_reuse(self):
        resource_request = ResourceRequest.objects.create(
            asset=self.asset,
            requester=self.user,
            destination_department=self.department,
            quantity=2,
            reason="Resource reuse testing.",
            status=ResourceRequest.Status.APPROVED,
        )

        source_approval = RequestApproval.objects.create(
            request=resource_request,
            approver=self.custodian,
            stage=RequestApproval.Stage.SOURCE,
            decision=RequestApproval.Decision.APPROVED,
        )

        reservation = Reservation.objects.create(
            request=resource_request,
            source_approval=source_approval,
            quantity=2,
            status=Reservation.Status.CONVERTED,
        )

        transfer = Transfer.objects.create(
            reservation=reservation,
            arranged_by=self.custodian,
            quantity=2,
            status=Transfer.Status.DISPATCHED,
            dispatched_at=timezone.now(),
        )

        summary = get_sustainability_summary()

        self.assertEqual(
            summary["reused_units"],
            0,
        )

        transfer.status = Transfer.Status.RECEIVED
        transfer.received_at = timezone.now()
        transfer.received_by = self.user
        transfer.save()

        summary = get_sustainability_summary()

        self.assertEqual(
            summary["reused_units"],
            2,
        )
