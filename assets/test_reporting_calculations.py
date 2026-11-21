
from django.contrib.auth import get_user_model
from django.test import TestCase

from assets.models import (
    Asset,
    AssetMaintenance,
    Category,
    Department,
)
from assets.services import register_asset
from assets.reporting_services import get_operational_report

from workflows.models import ResourceRequest


User = get_user_model()


class ReportingCalculationTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="report_metrics_user",
            password="TestPassword123!",
        )

        self.department = Department.objects.create(
            name="Reporting Engineering",
            code="REPENG",
        )

        self.category = Category.objects.create(
            name="Reporting Equipment",
        )

        self.asset = register_asset(
            name="Reporting Test Laptop",
            category=self.category,
            department=self.department,
            custodian=self.user,
            location="Engineering Lab",
            tracking_mode=Asset.TrackingMode.LOT,
            quantity=5,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.PUBLISHED,
        )

    def create_request(self, status):
        return ResourceRequest.objects.create(
            asset=self.asset,
            requester=self.user,
            destination_department=self.department,
            quantity=1,
            reason="Reporting calculation test.",
            status=status,
        )

    def test_total_assets(self):
        report = get_operational_report()

        self.assertEqual(report["total_assets"], 1)
        self.assertEqual(
            report["sustainability"]["available_units"],
            5,
        )

    def test_pending_requests(self):
        self.create_request(ResourceRequest.Status.PENDING)

        report = get_operational_report()

        self.assertEqual(report["total_requests"], 1)
        self.assertEqual(report["pending_requests"], 1)

    def test_request_status_counts(self):
        self.create_request(ResourceRequest.Status.APPROVED)
        self.create_request(ResourceRequest.Status.REJECTED)
        self.create_request(ResourceRequest.Status.EXPIRED)
        self.create_request(ResourceRequest.Status.CANCELLED)

        report = get_operational_report()

        self.assertEqual(report["total_requests"], 4)
        self.assertEqual(report["approved_requests"], 1)
        self.assertEqual(report["rejected_requests"], 1)
        self.assertEqual(report["expired_requests"], 1)
        self.assertEqual(report["cancelled_requests"], 1)

    def test_completed_maintenance_count(self):
        AssetMaintenance.objects.create(
            asset=self.asset,
            reported_by=self.user,
            title="Completed repair",
            description="Laptop repaired.",
            quantity=1,
            status=AssetMaintenance.Status.COMPLETED,
        )

        AssetMaintenance.objects.create(
            asset=self.asset,
            reported_by=self.user,
            title="Pending repair",
            description="Waiting for technician.",
            quantity=1,
            status=AssetMaintenance.Status.REPORTED,
        )

        report = get_operational_report()

        self.assertEqual(report["total_maintenance"], 2)
        self.assertEqual(report["completed_maintenance"], 1)
        self.assertEqual(
            report["sustainability"]["repaired_units"],
            1,
        )

    def test_no_transfers_returns_zero(self):
        report = get_operational_report()

        self.assertEqual(report["total_transfers"], 0)
        self.assertEqual(report["completed_transfers"], 0)
        self.assertEqual(report["transferred_units"], 0)
