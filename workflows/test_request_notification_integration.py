
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from assets.models import Asset, Category, Department
from assets.services import register_asset
from workflows.models import Notification, ResourceRequest
from workflows.services import submit_request


User = get_user_model()


class RequestNotificationIntegrationTests(TestCase):

    def setUp(self):
        requester_group, _ = Group.objects.get_or_create(
            name="Requester"
        )

        self.requester = User.objects.create_user(
            username="integration_requester",
            password="TestPassword123!",
        )
        self.requester.groups.add(requester_group)

        self.other_user = User.objects.create_user(
            username="integration_other",
            password="TestPassword123!",
        )

        self.custodian = User.objects.create_user(
            username="integration_custodian",
            password="TestPassword123!",
        )

        self.department = Department.objects.create(
            name="Integration Engineering",
            code="INTENG",
        )

        self.category = Category.objects.create(
            name="Integration Equipment",
        )

        self.asset = register_asset(
            name="Integration Laptop",
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

    def submit(self, requester=None, quantity=1):
        return submit_request(
            requester=(
                requester
                if requester is not None
                else self.requester
            ),
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=quantity,
            reason="Required for testing.",
        )

    def test_success_creates_one_notification(self):
        resource_request = self.submit()

        self.assertEqual(ResourceRequest.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 1)

        notification = Notification.objects.get()

        self.assertEqual(
            notification.recipient,
            self.requester,
        )
        self.assertEqual(
            notification.notification_type,
            Notification.NotificationType.REQUEST,
        )
        self.assertIn(
            str(resource_request.pk),
            notification.message,
        )
        self.assertFalse(notification.is_read)

    def test_notification_links_to_my_requests(self):
        self.submit()

        notification = Notification.objects.get()

        self.assertEqual(
            notification.target_url,
            reverse("my_requests"),
        )

        self.assertIn(
            self.asset.name,
            notification.message,
        )

    def test_invalid_role_creates_no_notification(self):
        with self.assertRaises(ValidationError):
            self.submit(requester=self.other_user)

        self.assertFalse(ResourceRequest.objects.exists())
        self.assertFalse(Notification.objects.exists())

    def test_insufficient_stock_creates_no_notification(self):
        with self.assertRaises(ValidationError):
            self.submit(quantity=6)

        self.assertFalse(ResourceRequest.objects.exists())
        self.assertFalse(Notification.objects.exists())

    def test_draft_asset_creates_no_notification(self):
        self.asset.publication = Asset.Publication.DRAFT
        self.asset.save(update_fields=["publication"])

        with self.assertRaises(ValidationError):
            self.submit()

        self.assertFalse(ResourceRequest.objects.exists())
        self.assertFalse(Notification.objects.exists())

    def test_notification_failure_rolls_back_request(self):
        with patch(
            "workflows.services.create_notification",
            side_effect=ValidationError(
                "Notification creation failed."
            ),
        ):
            with self.assertRaises(ValidationError):
                self.submit()

        self.assertFalse(ResourceRequest.objects.exists())
        self.assertFalse(Notification.objects.exists())
