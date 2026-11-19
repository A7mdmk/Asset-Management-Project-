
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase

from assets.models import Asset, Category, Department
from assets.services import register_asset

from .models import ResourceRequest, RequestApproval
from .services import submit_request, decide_request


class WorkflowModelTests(TestCase):

    def test_request_status_choices(self):
        self.assertEqual(
            ResourceRequest.Status.PENDING,
            "Pending"
        )

    def test_approval_decision_choices(self):
        self.assertEqual(
            RequestApproval.Decision.APPROVED,
            "Approved"
        )


class SubmitRequestTests(TestCase):

    def setUp(self):
        User = get_user_model()

        requester_group, _ = Group.objects.get_or_create(
            name="Requester"
        )

        self.requester = User.objects.create_user(
            username="workflow_requester",
            password="TestPassword123!"
        )
        self.requester.groups.add(requester_group)

        self.other_user = User.objects.create_user(
            username="workflow_other",
            password="TestPassword123!"
        )

        self.custodian = User.objects.create_user(
            username="workflow_custodian",
            password="TestPassword123!"
        )

        self.department = Department.objects.create(
            name="Engineering",
            code="ENG"
        )

        self.category = Category.objects.create(
            name="IT Equipment"
        )

        self.asset = register_asset(
            name="Laptop",
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

    def test_request_starts_pending_without_reserving_stock(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            quantity=2,
            reason="Needed for a university project",
        )

        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.PENDING
        )
        self.assertEqual(
            ResourceRequest.objects.count(), 1
        )

        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)

    def test_user_without_requester_role_cannot_submit(self):
        with self.assertRaises(ValidationError):
            submit_request(
                requester=self.other_user,
                asset_id=self.asset.pk,
                quantity=1,
                reason="Testing permissions",
            )

        self.assertEqual(
            ResourceRequest.objects.count(), 0
        )

    def test_request_exceeding_free_stock_is_rejected(self):
        with self.assertRaises(ValidationError):
            submit_request(
                requester=self.requester,
                asset_id=self.asset.pk,
                quantity=6,
                reason="Testing stock availability",
            )

        self.assertEqual(
            ResourceRequest.objects.count(), 0
        )

    def test_unpublished_asset_cannot_be_requested(self):
        self.asset.publication = Asset.Publication.DRAFT
        self.asset.save()

        with self.assertRaises(ValidationError):
            submit_request(
                requester=self.requester,
                asset_id=self.asset.pk,
                quantity=1,
                reason="Testing draft restriction",
            )

        self.assertEqual(
            ResourceRequest.objects.count(), 0
        )

    def test_unsafe_asset_cannot_be_requested(self):
        self.asset.condition = Asset.Condition.UNSAFE
        self.asset.save()

        with self.assertRaises(ValidationError):
            submit_request(
                requester=self.requester,
                asset_id=self.asset.pk,
                quantity=1,
                reason="Testing unsafe restriction",
            )

        self.assertEqual(
            ResourceRequest.objects.count(), 0
        )

    def test_zero_quantity_is_rejected(self):
        with self.assertRaises(ValidationError):
            submit_request(
                requester=self.requester,
                asset_id=self.asset.pk,
                quantity=0,
                reason="Testing invalid quantity",
            )

        self.assertEqual(
            ResourceRequest.objects.count(), 0
        )

    def test_inactive_requester_cannot_submit(self):
        self.requester.is_active = False
        self.requester.save()

        with self.assertRaises(ValidationError):
            submit_request(
                requester=self.requester,
                asset_id=self.asset.pk,
                quantity=1,
                reason="Testing inactive user",
            )

        self.assertEqual(
            ResourceRequest.objects.count(), 0
        )

class ApprovalWorkflowTests(SubmitRequestTests):

    def setUp(self):
        super().setUp()

        approver_group, _ = Group.objects.get_or_create(
            name="Approver/Admin"
        )

        self.approver = get_user_model().objects.create_user(
            username="workflow_approver",
            password="TestPassword123!"
        )
        self.approver.groups.add(approver_group)

    def test_approval_reserves_stock(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            quantity=2,
            reason="University project",
        )
    

        result = decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            decision=RequestApproval.Decision.APPROVED,
        )

        self.assertEqual(
            result.status,
            ResourceRequest.Status.APPROVED
        )

        self.asset.stock.refresh_from_db()

        self.assertEqual(self.asset.stock.free, 3)
        self.assertEqual(self.asset.stock.held, 2)
        self.assertEqual(self.asset.stock.total, 5)
        self.assertEqual(
            RequestApproval.objects.filter(
                request=resource_request
            ).count(),
            1
        )

    def test_rejection_does_not_reserve_stock(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            quantity=2,
            reason="University project",
        )

        result = decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            decision=RequestApproval.Decision.REJECTED,
        )

        self.assertEqual(
            result.status,
            ResourceRequest.Status.REJECTED
        )

        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)

    def test_requester_cannot_approve_own_request(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            quantity=1,
            reason="University project",
        )

        approver_group = Group.objects.get(
            name="Approver/Admin"
        )
        self.requester.groups.add(approver_group)

        with self.assertRaises(ValidationError):
            decide_request(
                approver=self.requester,
                request_id=resource_request.pk,
                decision=RequestApproval.Decision.APPROVED,
            )

        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(RequestApproval.objects.count(), 0)

    def test_request_cannot_be_approved_twice(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            quantity=2,
            reason="University project",
        )

        decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            decision=RequestApproval.Decision.APPROVED,
        )

        with self.assertRaises(ValidationError):
            decide_request(
                approver=self.approver,
                request_id=resource_request.pk,
                decision=RequestApproval.Decision.APPROVED,
            )

        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 3)
        self.assertEqual(self.asset.stock.held, 2)
        self.assertEqual(RequestApproval.objects.count(), 1)

    def test_approval_cannot_reserve_more_than_available(self):
        first_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            quantity=4,
            reason="First request",
        )

        second_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            quantity=3,
            reason="Second request",
        )

        decide_request(
            approver=self.approver,
            request_id=first_request.pk,
            decision=RequestApproval.Decision.APPROVED,
        )

        with self.assertRaises(ValidationError):
            decide_request(
                approver=self.approver,
                request_id=second_request.pk,
                decision=RequestApproval.Decision.APPROVED,
            )

        second_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            second_request.status,
            ResourceRequest.Status.PENDING
        )
        self.assertEqual(self.asset.stock.free, 1)
        self.assertEqual(self.asset.stock.held, 4)
        self.assertEqual(self.asset.stock.total, 5)
        self.assertEqual(RequestApproval.objects.count(), 1)
