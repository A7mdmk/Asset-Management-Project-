
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import DepartmentApprover
from assets.models import Asset, Category, Department
from assets.services import register_asset
from workflows.models import (
    Notification,
    RequestApproval,
    ResourceRequest,
    Reservation,
)
from workflows.services import (
    submit_request,
    decide_request,
)


User = get_user_model()


class ApprovalNotificationIntegrationTests(TestCase):

    def setUp(self):
        requester_group, _ = Group.objects.get_or_create(
            name="Requester"
        )
        approver_group, _ = Group.objects.get_or_create(
            name="Approver/Admin"
        )
        custodian_group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.requester = User.objects.create_user(
            username="notif_approval_requester",
            password="TestPassword123!",
        )
        self.requester.groups.add(requester_group)

        self.approver = User.objects.create_user(
            username="notif_destination_approver",
            password="TestPassword123!",
        )
        self.approver.groups.add(approver_group)

        self.custodian = User.objects.create_user(
            username="notif_source_custodian",
            password="TestPassword123!",
        )
        self.custodian.groups.add(custodian_group)

        self.department = Department.objects.create(
            name="Notification Engineering",
            code="NOTENG",
        )

        self.category = Category.objects.create(
            name="Notification Equipment",
        )

        DepartmentApprover.objects.create(
            department=self.department,
            user=self.approver,
            is_active=True,
        )

        self.asset = register_asset(
            name="Notification Test Laptop",
            category=self.category,
            department=self.department,
            custodian=self.custodian,
            location="Engineering Lab",
            tracking_mode=Asset.TrackingMode.LOT,
            quantity=5,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.PUBLISHED,
        )

        self.resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="University project",
        )

    def approval_notifications(self):
        return Notification.objects.filter(
            recipient=self.requester,
            notification_type=(
                Notification.NotificationType.APPROVAL
            ),
        )

    def destination_decision(
        self,
        decision=RequestApproval.Decision.APPROVED,
        comment="",
    ):
        return decide_request(
            approver=self.approver,
            request_id=self.resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=decision,
            comment=comment,
        )

    def source_decision(
        self,
        decision=RequestApproval.Decision.APPROVED,
        comment="",
    ):
        return decide_request(
            approver=self.custodian,
            request_id=self.resource_request.pk,
            stage=RequestApproval.Stage.SOURCE,
            decision=decision,
            comment=comment,
        )

    def test_destination_approval_creates_notification(self):
        result = self.destination_decision()

        self.assertEqual(
            result.status,
            ResourceRequest.Status.PENDING,
        )

        self.assertEqual(
            self.approval_notifications().count(),
            1,
        )

        notification = self.approval_notifications().get()

        self.assertEqual(
            notification.title,
            "Destination Approval Completed",
        )

        self.assertFalse(notification.is_read)

        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)

    def test_final_approval_creates_notification(self):
        self.destination_decision()
        result = self.source_decision()

        self.assertEqual(
            result.status,
            ResourceRequest.Status.APPROVED,
        )

        self.assertEqual(
            self.approval_notifications().count(),
            2,
        )

        self.assertTrue(
            self.approval_notifications().filter(
                title="Resource Request Approved"
            ).exists()
        )

        self.assertEqual(
            Reservation.objects.filter(
                request=self.resource_request
            ).count(),
            1,
        )

        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 3)
        self.assertEqual(self.asset.stock.held, 2)

    def test_destination_rejection_creates_notification(self):
        result = self.destination_decision(
            decision=RequestApproval.Decision.REJECTED,
            comment="Resource unavailable.",
        )

        self.assertEqual(
            result.status,
            ResourceRequest.Status.REJECTED,
        )

        self.assertEqual(
            self.approval_notifications().count(),
            1,
        )

        notification = self.approval_notifications().get()

        self.assertEqual(
            notification.title,
            "Resource Request Rejected",
        )

        self.assertIn(
            "Destination",
            notification.message,
        )

        self.assertFalse(Reservation.objects.exists())

    def test_source_rejection_creates_notification(self):
        self.destination_decision()

        result = self.source_decision(
            decision=RequestApproval.Decision.REJECTED,
            comment="Source release unavailable.",
        )

        self.assertEqual(
            result.status,
            ResourceRequest.Status.REJECTED,
        )

        self.assertEqual(
            self.approval_notifications().count(),
            2,
        )

        self.assertTrue(
            self.approval_notifications().filter(
                title="Resource Request Rejected"
            ).exists()
        )

        self.assertFalse(Reservation.objects.exists())

        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)

    def test_duplicate_approval_creates_no_extra_notification(self):
        self.destination_decision()

        before = self.approval_notifications().count()

        with self.assertRaises(ValidationError):
            self.destination_decision()

        self.assertEqual(
            self.approval_notifications().count(),
            before,
        )

        self.assertEqual(
            RequestApproval.objects.filter(
                request=self.resource_request
            ).count(),
            1,
        )

    def test_expired_request_creates_no_approval_notification(self):
        self.resource_request.expires_at = (
            timezone.now() - timedelta(minutes=1)
        )
        self.resource_request.save(
            update_fields=["expires_at"]
        )

        result = self.destination_decision()

        self.assertEqual(
            result.status,
            ResourceRequest.Status.EXPIRED,
        )

        self.assertEqual(
            self.approval_notifications().count(),
            0,
        )

        self.assertFalse(
            RequestApproval.objects.filter(
                request=self.resource_request
            ).exists()
        )
