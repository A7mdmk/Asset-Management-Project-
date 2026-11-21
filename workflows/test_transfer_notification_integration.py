
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import DepartmentApprover
from assets.models import Asset, Category, Department
from assets.services import register_asset

from workflows.models import (
    Notification,
    RequestApproval,
    Reservation,
    Transfer,
)
from workflows.services import (
    submit_request,
    decide_request,
    arrange_transfer,
)


User = get_user_model()


class TransferNotificationIntegrationTests(TestCase):

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
            username="transfer_notif_requester",
            password="TestPassword123!",
        )
        self.requester.groups.add(requester_group)

        self.approver = User.objects.create_user(
            username="transfer_notif_approver",
            password="TestPassword123!",
        )
        self.approver.groups.add(approver_group)

        self.custodian = User.objects.create_user(
            username="transfer_notif_custodian",
            password="TestPassword123!",
        )
        self.custodian.groups.add(custodian_group)

        self.other_user = User.objects.create_user(
            username="transfer_notif_other",
            password="TestPassword123!",
        )

        self.department = Department.objects.create(
            name="Transfer Notification Department",
            code="TRNOT",
        )

        self.category = Category.objects.create(
            name="Transfer Notification Equipment",
        )

        DepartmentApprover.objects.create(
            department=self.department,
            user=self.approver,
            is_active=True,
        )

        self.asset = register_asset(
            name="Transfer Notification Laptop",
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

        decide_request(
            approver=self.approver,
            request_id=self.resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        decide_request(
            approver=self.custodian,
            request_id=self.resource_request.pk,
            stage=RequestApproval.Stage.SOURCE,
            decision=RequestApproval.Decision.APPROVED,
        )

        self.reservation = Reservation.objects.get(
            request=self.resource_request
        )

    def transfer_notifications(self):
        return Notification.objects.filter(
            recipient=self.requester,
            notification_type=Notification.NotificationType.TRANSFER,
        )

    def arrange(self, actor=None):
        return arrange_transfer(
            actor=actor if actor is not None else self.custodian,
            reservation_id=self.reservation.pk,
        )

    def test_arrangement_creates_one_notification(self):
        transfer = self.arrange()

        self.assertEqual(
            transfer.status,
            Transfer.Status.ARRANGED,
        )
        self.assertEqual(
            self.transfer_notifications().count(),
            1,
        )

        notification = self.transfer_notifications().get()

        self.assertEqual(
            notification.title,
            "Asset Transfer Arranged",
        )
        self.assertFalse(notification.is_read)
        self.assertIn(
            str(transfer.pk),
            notification.message,
        )

    def test_notification_contains_asset_and_link(self):
        self.arrange()

        notification = self.transfer_notifications().get()

        self.assertIn(
            self.asset.name,
            notification.message,
        )
        self.assertEqual(
            notification.target_url,
            reverse("my_requests"),
        )

    def test_arrangement_preserves_held_stock(self):
        self.arrange()

        self.asset.stock.refresh_from_db()

        self.assertEqual(self.asset.stock.free, 3)
        self.assertEqual(self.asset.stock.held, 2)

        self.reservation.refresh_from_db()

        self.assertEqual(
            self.reservation.status,
            Reservation.Status.CONVERTED,
        )

        self.assertEqual(
            self.transfer_notifications().count(),
            1,
        )

    def test_duplicate_arrangement_creates_no_extra_notification(self):
        self.arrange()

        with self.assertRaises(ValidationError):
            self.arrange()

        self.assertEqual(Transfer.objects.count(), 1)
        self.assertEqual(
            self.transfer_notifications().count(),
            1,
        )

    def test_unauthorized_user_cannot_create_notification(self):
        with self.assertRaises(ValidationError):
            self.arrange(actor=self.other_user)

        self.assertFalse(Transfer.objects.exists())
        self.assertFalse(
            self.transfer_notifications().exists()
        )

        self.reservation.refresh_from_db()

        self.assertEqual(
            self.reservation.status,
            Reservation.Status.APPROVED,
        )

    def test_notification_failure_rolls_back_transfer(self):
        with patch(
            "workflows.services.create_notification",
            side_effect=ValidationError(
                "Notification creation failed."
            ),
        ):
            with self.assertRaises(ValidationError):
                self.arrange()

        self.assertFalse(Transfer.objects.exists())

        self.reservation.refresh_from_db()

        self.assertEqual(
            self.reservation.status,
            Reservation.Status.APPROVED,
        )

        self.assertFalse(
            self.transfer_notifications().exists()
        )
