from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from assets.models import Asset, Category, Department
from assets.services import register_asset
from workflows.models import Notification, RequestApproval, ResourceRequest, Reservation
from workflows.notification_services import create_notification
from workflows.services import decide_request


class ExpirationFixture:
    def setUp(self):
        self.requester = get_user_model().objects.create_user(
            username="expiry_requester"
        )
        self.approver = get_user_model().objects.create_user(
            username="expiry_approver"
        )
        self.department = Department.objects.create(name="Expiry", code="EXP")
        self.asset = register_asset(
            name="Expiry Laptop",
            category=Category.objects.create(name="Expiry Equipment"),
            department=self.department,
            custodian=self.approver,
            location="Lab",
            tracking_mode=Asset.TrackingMode.LOT,
            quantity=5,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.PUBLISHED,
        )
        self.now = timezone.now()
        self.request = self.make_request()

    def make_request(self, **overrides):
        fields = dict(
            asset=self.asset,
            requester=self.requester,
            destination_department=self.department,
            quantity=2,
            reason="Expiry test",
            expires_at=self.now - timedelta(minutes=1),
        )
        fields.update(overrides)
        return ResourceRequest.objects.create(**fields)

    def run_command(self):
        output = StringIO()
        call_command("expire_requests", stdout=output, no_color=True)
        return output.getvalue()

    def decide(self):
        return decide_request(
            approver=self.approver,
            request_id=self.request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )


class ExpirationNotificationTests(ExpirationFixture, TestCase):
    def test_expiry_creates_matching_notification_without_stock_changes(self):
        with patch(
            "workflows.management.commands.expire_requests.timezone.now",
            return_value=self.now,
        ):
            self.assertIn("Expired 1 pending request(s).", self.run_command())
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ResourceRequest.Status.EXPIRED)
        self.assertEqual(self.request.updated_at, self.now)
        notification = Notification.objects.get()
        self.assertEqual(notification.recipient, self.requester)
        self.assertEqual(notification.notification_type, Notification.NotificationType.REQUEST)
        self.assertEqual(notification.title, "Resource Request Expired")
        self.assertEqual(notification.message, (
            f"Your request #{self.request.pk} for {self.asset.name} has expired "
            "because it was not fully approved within 48 hours."
        ))
        self.assertEqual(notification.target_url, reverse("my_requests"))
        self.assertFalse(notification.is_read)
        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(RequestApproval.objects.exists())

    def test_repeated_command_does_not_duplicate_notifications(self):
        self.run_command()
        self.assertIn("Expired 0 pending request(s).", self.run_command())
        self.assertEqual(Notification.objects.count(), 1)

    def test_only_pending_requests_at_or_before_deadline_expire(self):
        future = self.make_request(expires_at=self.now + timedelta(seconds=1))
        boundary = self.make_request(expires_at=self.now)
        terminal = [self.make_request(status=status) for status in (
            ResourceRequest.Status.APPROVED,
            ResourceRequest.Status.REJECTED,
            ResourceRequest.Status.CANCELLED,
            ResourceRequest.Status.EXPIRED,
        )]
        with patch(
            "workflows.management.commands.expire_requests.timezone.now",
            return_value=self.now,
        ):
            self.assertIn("Expired 2 pending request(s).", self.run_command())
        future.refresh_from_db()
        boundary.refresh_from_db()
        self.assertEqual(future.status, ResourceRequest.Status.PENDING)
        self.assertEqual(boundary.status, ResourceRequest.Status.EXPIRED)
        for request in terminal:
            original_status = request.status
            request.refresh_from_db()
            self.assertEqual(request.status, original_status)
        self.assertEqual(Notification.objects.count(), 2)

    def test_inactive_requester_expires_without_notification(self):
        self.requester.is_active = False
        self.requester.save(update_fields=["is_active"])
        self.assertIn("Expired 1 pending request(s).", self.run_command())
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ResourceRequest.Status.EXPIRED)
        self.assertFalse(Notification.objects.exists())

    def test_notification_failure_rolls_back_entire_batch_and_can_retry(self):
        second = self.make_request()
        initial_updated_at = self.request.updated_at
        with patch(
            "workflows.management.commands.expire_requests.create_notification",
            side_effect=[None, RuntimeError("Notification failed")],
        ) as notify:
            # Persist the first notification to test rollback of real writes.
            def create_then_fail(**kwargs):
                if notify.call_count == 1:
                    return create_notification(**kwargs)
                raise RuntimeError("Notification failed")
            notify.side_effect = create_then_fail
            with self.assertRaisesMessage(RuntimeError, "Notification failed"):
                self.run_command()
        for request in (self.request, second):
            request.refresh_from_db()
            self.assertEqual(request.status, ResourceRequest.Status.PENDING)
        self.assertEqual(self.request.updated_at, initial_updated_at)
        self.assertFalse(Notification.objects.exists())
        self.run_command()
        self.assertEqual(Notification.objects.count(), 2)

    def test_decision_expiry_then_command_notifies_once(self):
        self.decide()
        self.assertIn("Expired 0 pending request(s).", self.run_command())
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(Notification.objects.get().title, "Resource Request Expired")

    def test_command_expiry_then_decision_notifies_once(self):
        self.run_command()
        with self.assertRaises(ValidationError):
            self.decide()
        self.assertEqual(Notification.objects.count(), 1)


@skipUnlessDBFeature("has_select_for_update")
class ConcurrentExpirationTests(ExpirationFixture, TransactionTestCase):
    def test_two_command_workers_notify_once(self):
        self.run_workers("command", "command")

    def test_command_and_decision_notify_once(self):
        self.run_workers("command", "decision")

    def run_workers(self, *actions):
        barrier = Barrier(2)

        def worker(action):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                if action == "command":
                    self.run_command()
                else:
                    try:
                        self.decide()
                    except ValidationError:
                        # The command may have already expired the request.
                        current = ResourceRequest.objects.get(pk=self.request.pk)
                        if current.status != ResourceRequest.Status.EXPIRED:
                            raise
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, action) for action in actions]
            for future in futures:
                future.result(timeout=30)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ResourceRequest.Status.EXPIRED)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertFalse(RequestApproval.objects.exists())
