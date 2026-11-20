
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from accounts.models import DepartmentApprover
from assets.models import Asset, Category, Department
from assets.services import register_asset

from .models import ResourceRequest, RequestApproval, Reservation
from .services import (
    submit_request,
    decide_request,
    cancel_pending_request,
    cancel_approved_reservation,
)


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
            destination_department_id=self.department.pk,
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
            destination_department_id=self.department.pk,
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
            destination_department_id=self.department.pk,
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
            destination_department_id=self.department.pk,
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
            destination_department_id=self.department.pk,
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
            destination_department_id=self.department.pk,
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
            destination_department_id=self.department.pk,
                quantity=1,
                reason="Testing inactive user",
            )

        self.assertEqual(
            ResourceRequest.objects.count(), 0
        )


class ApprovalWorkflowTests(SubmitRequestTests):


    def setUp(self):
        super().setUp()

        User = get_user_model()

        approver_group, _ = Group.objects.get_or_create(
            name="Approver/Admin"
        )

        custodian_group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        # Stage 1: Destination department approver
        self.approver = User.objects.create_user(
            username="workflow_approver",
            password="TestPassword123!"
        )

        self.approver.groups.add(approver_group)

        DepartmentApprover.objects.create(
            department=self.department,
            user=self.approver,
            is_active=True,
        )

        # Stage 2: Assigned source custodian
        self.custodian.groups.add(custodian_group)

        # The two approvers are different people.
        self.assertNotEqual(
            self.approver.pk,
            self.custodian.pk,
        )



    def test_approval_reserves_stock(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="University project",
        )

        # Stage 1: Destination acceptance
        result = decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        # Request remains pending after the first approval.
        self.assertEqual(
            result.status,
            ResourceRequest.Status.PENDING,
        )

        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)

        # Stage 2: Source custodian release
        result = decide_request(
            approver=self.custodian,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.SOURCE,
            decision=RequestApproval.Decision.APPROVED,
        )

        # Request is approved only after both stages.
        self.assertEqual(
            result.status,
            ResourceRequest.Status.APPROVED,
        )

        self.asset.stock.refresh_from_db()

        self.assertEqual(self.asset.stock.free, 3)
        self.assertEqual(self.asset.stock.held, 2)
        self.assertEqual(self.asset.stock.total, 5)

        self.assertEqual(
            RequestApproval.objects.filter(
                request=resource_request
            ).count(),
            2,
        )

        self.assertEqual(
            set(
                RequestApproval.objects.filter(
                    request=resource_request
                ).values_list("stage", flat=True)
            ),
            {
                RequestApproval.Stage.DESTINATION,
                RequestApproval.Stage.SOURCE,
            },
        )


    def test_rejection_does_not_reserve_stock(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="University project",
        )

        result = decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.REJECTED,
            comment="The destination cannot accept this asset.",
        )

        self.assertEqual(
            result.status,
            ResourceRequest.Status.REJECTED,
        )

        self.asset.stock.refresh_from_db()

        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.total, 5)

        self.assertEqual(
            RequestApproval.objects.filter(
                request=resource_request,
                stage=RequestApproval.Stage.DESTINATION,
                decision=RequestApproval.Decision.REJECTED,
            ).count(),
            1,
        )



    def test_requester_cannot_approve_own_request(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=1,
            reason="Testing self-approval protection",
        )

        # Give the requester an approver role and department assignment.
        approver_group = Group.objects.get(
            name="Approver/Admin"
        )
        self.requester.groups.add(approver_group)

        DepartmentApprover.objects.create(
            department=self.department,
            user=self.requester,
            is_active=True,
        )

        # The requester must still be unable to approve.
        with self.assertRaises(ValidationError):
            decide_request(
                approver=self.requester,
                request_id=resource_request.pk,
                stage=RequestApproval.Stage.DESTINATION,
                decision=RequestApproval.Decision.APPROVED,
            )

        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.PENDING,
        )
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(RequestApproval.objects.count(), 0)



    def test_request_cannot_be_approved_twice(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing duplicate approvals",
        )

        # First destination acceptance succeeds.
        decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        # Repeating the same stage must fail.
        with self.assertRaises(ValidationError):
            decide_request(
                approver=self.approver,
                request_id=resource_request.pk,
                stage=RequestApproval.Stage.DESTINATION,
                decision=RequestApproval.Decision.APPROVED,
            )

        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.PENDING,
        )

        # Destination acceptance must not reserve stock.
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.total, 5)

        # Only the original destination decision exists.
        self.assertEqual(
            RequestApproval.objects.filter(
                request=resource_request
            ).count(),
            1,
        )



    def test_approval_cannot_reserve_more_than_available(self):
        first_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=4,
            reason="First request",
        )

        second_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=3,
            reason="Second request",
        )

        # Stage 1: Accept both requests without reserving stock.
        for resource_request in (first_request, second_request):
            decide_request(
                approver=self.approver,
                request_id=resource_request.pk,
                stage=RequestApproval.Stage.DESTINATION,
                decision=RequestApproval.Decision.APPROVED,
            )

        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)

        # Stage 2: Release four units for the first request.
        decide_request(
            approver=self.custodian,
            request_id=first_request.pk,
            stage=RequestApproval.Stage.SOURCE,
            decision=RequestApproval.Decision.APPROVED,
        )

        # Only one unit remains, so the second release must fail.
        with self.assertRaises(ValidationError):
            decide_request(
                approver=self.custodian,
                request_id=second_request.pk,
                stage=RequestApproval.Stage.SOURCE,
                decision=RequestApproval.Decision.APPROVED,
            )

        first_request.refresh_from_db()
        second_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            first_request.status,
            ResourceRequest.Status.APPROVED,
        )
        self.assertEqual(
            second_request.status,
            ResourceRequest.Status.PENDING,
        )

        self.assertEqual(self.asset.stock.free, 1)
        self.assertEqual(self.asset.stock.held, 4)
        self.assertEqual(self.asset.stock.total, 5)

        # Two destination decisions and one source release.
        self.assertEqual(RequestApproval.objects.count(), 3)



    def test_expired_request_cannot_be_approved(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing expiration",
        )

        # Stage 1: Destination accepts the request.
        decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)

        # Simulate the 48-hour deadline having passed.
        resource_request.expires_at = (
            timezone.now() - timedelta(minutes=1)
        )
        resource_request.save(update_fields=["expires_at"])

        # Stage 2: The source custodian attempts to release.
        result = decide_request(
            approver=self.custodian,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.SOURCE,
            decision=RequestApproval.Decision.APPROVED,
        )

        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            result.status,
            ResourceRequest.Status.EXPIRED,
        )
        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.EXPIRED,
        )

        # No stock may be reserved after expiration.
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.total, 5)

        # Only the earlier destination acceptance exists.
        self.assertEqual(RequestApproval.objects.count(), 1)
        self.assertFalse(
            RequestApproval.objects.filter(
                request=resource_request,
                stage=RequestApproval.Stage.SOURCE,
            ).exists()
        )


    def test_expiration_command_expires_overdue_requests(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing expiration command",
        )

        resource_request.expires_at = (
            timezone.now() - timedelta(minutes=1)
        )
        resource_request.save(update_fields=["expires_at"])

        call_command("expire_requests", verbosity=0)

        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.EXPIRED
        )
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(RequestApproval.objects.count(), 0)


    def test_unauthorized_user_cannot_approve_request(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing approval permissions",
        )

        # Give the user the Approver/Admin role,
        # but no authorization for the destination department.
        approver_group = Group.objects.get(
            name="Approver/Admin"
        )
        self.other_user.groups.add(approver_group)

        with self.assertRaises(ValidationError):
            decide_request(
                approver=self.other_user,
                request_id=resource_request.pk,
                stage=RequestApproval.Stage.DESTINATION,
                decision=RequestApproval.Decision.APPROVED,
            )

        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.PENDING,
        )

        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)

        self.assertEqual(
            RequestApproval.objects.count(),
            0,
        )



    def test_failed_approval_preserves_stock_and_request(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing transaction rollback",
        )

        # Stage 1: Destination accepts the request.
        decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        # Asset becomes unavailable before source release.
        self.asset.publication = Asset.Publication.WITHDRAWN
        self.asset.save(update_fields=["publication"])

        # Stage 2: Source release must fail.
        with self.assertRaises(ValidationError):
            decide_request(
                approver=self.custodian,
                request_id=resource_request.pk,
                stage=RequestApproval.Stage.SOURCE,
                decision=RequestApproval.Decision.APPROVED,
            )

        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        # Request remains pending; stock is unchanged.
        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.PENDING,
        )

        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.total, 5)

        # Only the destination approval was recorded.
        self.assertEqual(
            RequestApproval.objects.filter(
                request=resource_request,
                stage=RequestApproval.Stage.DESTINATION,
            ).count(),
            1,
        )

        self.assertFalse(
            RequestApproval.objects.filter(
                request=resource_request,
                stage=RequestApproval.Stage.SOURCE,
            ).exists()
        )



    def test_database_error_rolls_back_stock_reservation(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing atomic rollback",
        )

        # Stage 1: Destination acceptance succeeds.
        decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        # Stage 2: Simulate a database failure when saving
        # the source approval, after stock has been updated.
        with patch.object(
            RequestApproval,
            "save",
            side_effect=RuntimeError("Simulated database failure"),
        ):
            with self.assertRaises(RuntimeError):
                decide_request(
                    approver=self.custodian,
                    request_id=resource_request.pk,
                    stage=RequestApproval.Stage.SOURCE,
                    decision=RequestApproval.Decision.APPROVED,
                )

        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        # The failed transaction must undo the stock movement.
        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.PENDING,
        )

        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.total, 5)

        # Destination acceptance remains recorded.
        self.assertEqual(
            RequestApproval.objects.filter(
                request=resource_request,
                stage=RequestApproval.Stage.DESTINATION,
            ).count(),
            1,
        )

        # The failed source approval must not be recorded.
        self.assertFalse(
            RequestApproval.objects.filter(
                request=resource_request,
                stage=RequestApproval.Stage.SOURCE,
            ).exists()
        )

    def test_requester_can_cancel_pending_request(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing pending cancellation",
        )

        result = cancel_pending_request(
            requester=self.requester,
            request_id=resource_request.pk,
        )

        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            result.status,
            ResourceRequest.Status.CANCELLED,
        )

        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.CANCELLED,
        )

        # Pending cancellation must not change stock.
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.total, 5)

        # Cancellation does not create an approval.
        self.assertEqual(
            RequestApproval.objects.filter(
                request=resource_request
            ).count(),
            0,
        )

    def test_other_user_cannot_cancel_pending_request(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing unauthorized cancellation",
        )

        # Another user attempts to cancel the request.
        with self.assertRaises(ValidationError):
            cancel_pending_request(
                requester=self.other_user,
                request_id=resource_request.pk,
            )

        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        # The request and stock must remain unchanged.
        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.PENDING,
        )

        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.total, 5)

        self.assertEqual(
            RequestApproval.objects.filter(
                request=resource_request
            ).count(),
            0,
        )

    def test_pending_request_cannot_be_cancelled_twice(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing duplicate cancellation",
        )

        # First cancellation succeeds.
        cancel_pending_request(
            requester=self.requester,
            request_id=resource_request.pk,
        )

        # Second cancellation must be rejected.
        with self.assertRaises(ValidationError):
            cancel_pending_request(
                requester=self.requester,
                request_id=resource_request.pk,
            )

        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.CANCELLED,
        )

        # Neither cancellation changes stock.
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.total, 5)

        self.assertEqual(
            RequestApproval.objects.filter(
                request=resource_request
            ).count(),
            0,
        )

    def test_approved_request_cannot_use_pending_cancellation(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing cancellation after approval",
        )

        # Stage 1: Destination acceptance
        decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        # Stage 2: Source custodian release
        decide_request(
            approver=self.custodian,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.SOURCE,
            decision=RequestApproval.Decision.APPROVED,
        )

        # Pending-only cancellation must be rejected.
        with self.assertRaises(ValidationError):
            cancel_pending_request(
                requester=self.requester,
                request_id=resource_request.pk,
            )

        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.APPROVED,
        )

        # The existing reservation must remain intact.
        self.assertEqual(self.asset.stock.free, 3)
        self.assertEqual(self.asset.stock.held, 2)
        self.assertEqual(self.asset.stock.total, 5)

        self.assertEqual(
            RequestApproval.objects.filter(
                request=resource_request
            ).count(),
            2,
        )

    def test_final_source_approval_creates_reservation(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing reservation creation",
        )

        # Stage 1: Destination acceptance
        decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        # No reservation before final source approval.
        self.assertFalse(
            Reservation.objects.filter(
                request=resource_request
            ).exists()
        )

        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)

        # Stage 2: Final source release
        decide_request(
            approver=self.custodian,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.SOURCE,
            decision=RequestApproval.Decision.APPROVED,
        )

        resource_request.refresh_from_db()
        reservation = Reservation.objects.get(
            request=resource_request
        )

        source_approval = RequestApproval.objects.get(
            request=resource_request,
            stage=RequestApproval.Stage.SOURCE,
        )

        self.assertEqual(
            reservation.status,
            Reservation.Status.APPROVED,
        )
        self.assertEqual(reservation.quantity, 2)
        self.assertEqual(
            reservation.source_approval_id,
            source_approval.pk,
        )

        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.APPROVED,
        )

        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 3)
        self.assertEqual(self.asset.stock.held, 2)
        self.assertEqual(self.asset.stock.total, 5)

        # Exactly one reservation exists.
        self.assertEqual(
            Reservation.objects.filter(
                request=resource_request
            ).count(),
            1,
        )

    def test_failed_reservation_save_rolls_back_approval_and_stock(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing reservation rollback",
        )

        # Stage 1: Destination accepts the request.
        decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        # Stage 2: Simulate failure when saving the reservation.
        with patch.object(
            Reservation,
            "save",
            side_effect=RuntimeError("Simulated reservation failure"),
        ):
            with self.assertRaises(RuntimeError):
                decide_request(
                    approver=self.custodian,
                    request_id=resource_request.pk,
                    stage=RequestApproval.Stage.SOURCE,
                    decision=RequestApproval.Decision.APPROVED,
                )

        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        # The final approval must be rolled back.
        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.PENDING,
        )

        # Stock must return to its original values.
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.total, 5)

        # The earlier destination approval remains.
        self.assertEqual(
            RequestApproval.objects.filter(
                request=resource_request,
                stage=RequestApproval.Stage.DESTINATION,
            ).count(),
            1,
        )

        # The failed source approval must not exist.
        self.assertFalse(
            RequestApproval.objects.filter(
                request=resource_request,
                stage=RequestApproval.Stage.SOURCE,
            ).exists()
        )

        # No incomplete reservation may remain.
        self.assertFalse(
            Reservation.objects.filter(
                request=resource_request
            ).exists()
        )

    def test_approved_reservation_cancellation_releases_stock(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing approved cancellation",
        )

        # Stage 1: Destination acceptance
        decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        # Stage 2: Source release and reservation
        decide_request(
            approver=self.custodian,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.SOURCE,
            decision=RequestApproval.Decision.APPROVED,
        )

        reservation = Reservation.objects.get(
            request=resource_request
        )

        self.asset.stock.refresh_from_db()
        self.assertEqual(self.asset.stock.free, 3)
        self.assertEqual(self.asset.stock.held, 2)

        # The original requester cancels before dispatch.
        cancel_approved_reservation(
            actor=self.requester,
            reservation_id=reservation.pk,
            reason="Resource is no longer needed",
        )

        reservation.refresh_from_db()
        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            reservation.status,
            Reservation.Status.CANCELLED,
        )

        self.assertEqual(
            reservation.cancellation_reason,
            "Resource is no longer needed",
        )

        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.CANCELLED,
        )

        # Held stock returns to Free exactly once.
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.blocked, 0)
        self.assertEqual(self.asset.stock.total, 5)

        # Existing approval history remains intact.
        self.assertEqual(
            RequestApproval.objects.filter(
                request=resource_request
            ).count(),
            2,
        )

    def test_unsafe_reservation_cancellation_blocks_stock(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing unsafe cancellation",
        )

        # Stage 1: Destination acceptance
        decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        # Stage 2: Source release creates the reservation.
        decide_request(
            approver=self.custodian,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.SOURCE,
            decision=RequestApproval.Decision.APPROVED,
        )

        reservation = Reservation.objects.get(
            request=resource_request
        )

        # Asset becomes unsafe after approval.
        self.asset.condition = Asset.Condition.UNSAFE
        self.asset.save(update_fields=["condition"])

        # Cancellation must not return unsafe stock to Free.
        cancel_approved_reservation(
            actor=self.requester,
            reservation_id=reservation.pk,
            reason="Asset failed safety inspection",
        )

        reservation.refresh_from_db()
        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            reservation.status,
            Reservation.Status.CANCELLED,
        )

        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.CANCELLED,
        )

        self.assertEqual(self.asset.stock.free, 3)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.blocked, 2)
        self.assertEqual(self.asset.stock.total, 5)

    def test_unauthorized_user_cannot_cancel_reservation(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing cancellation authorization",
        )

        # Stage 1: Destination acceptance
        decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        # Stage 2: Source release
        decide_request(
            approver=self.custodian,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.SOURCE,
            decision=RequestApproval.Decision.APPROVED,
        )

        reservation = Reservation.objects.get(
            request=resource_request
        )

        # An unrelated user attempts cancellation.
        with self.assertRaises(ValidationError):
            cancel_approved_reservation(
                actor=self.other_user,
                reservation_id=reservation.pk,
                reason="Unauthorized cancellation attempt",
            )

        reservation.refresh_from_db()
        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        # Everything must remain unchanged.
        self.assertEqual(
            reservation.status,
            Reservation.Status.APPROVED,
        )

        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.APPROVED,
        )

        self.assertEqual(self.asset.stock.free, 3)
        self.assertEqual(self.asset.stock.held, 2)
        self.assertEqual(self.asset.stock.total, 5)

        self.assertEqual(
            RequestApproval.objects.filter(
                request=resource_request
            ).count(),
            2,
        )
    def test_unauthorized_user_cannot_cancel_approved_reservation(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing cancellation permissions",
        )

        decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        decide_request(
            approver=self.custodian,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.SOURCE,
            decision=RequestApproval.Decision.APPROVED,
        )

        reservation = Reservation.objects.get(
            request=resource_request
        )

        # Destination approver is neither requester nor custodian.
        with self.assertRaises(ValidationError):
            cancel_approved_reservation(
                actor=self.approver,
                reservation_id=reservation.pk,
                reason="Unauthorized cancellation attempt",
            )

        reservation.refresh_from_db()
        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        # Nothing must change after the rejected attempt.
        self.assertEqual(
            reservation.status,
            Reservation.Status.APPROVED,
        )
        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.APPROVED,
        )
        self.assertEqual(self.asset.stock.free, 3)
        self.assertEqual(self.asset.stock.held, 2)
        self.assertEqual(self.asset.stock.blocked, 0)

    def test_cannot_cancel_approved_reservation_twice(self):
        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing duplicate cancellation",
        )

        decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        decide_request(
            approver=self.custodian,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.SOURCE,
            decision=RequestApproval.Decision.APPROVED,
        )

        reservation = Reservation.objects.get(
            request=resource_request
        )

        # First cancellation succeeds.
        cancel_approved_reservation(
            actor=self.requester,
            reservation_id=reservation.pk,
            reason="No longer needed",
        )

        # Second cancellation must be rejected.
        with self.assertRaises(ValidationError):
            cancel_approved_reservation(
                actor=self.requester,
                reservation_id=reservation.pk,
                reason="Trying again",
            )

        reservation.refresh_from_db()
        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            reservation.status,
            Reservation.Status.CANCELLED,
        )
        self.assertEqual(
            reservation.cancellation_reason,
            "No longer needed",
        )
        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.CANCELLED,
        )

        # Stock was released exactly once.
        self.assertEqual(self.asset.stock.free, 5)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.blocked, 0)
        self.assertEqual(self.asset.stock.total, 5)

    def test_reservation_cancellation_failure_rolls_back_stock(self):
        from unittest.mock import patch

        resource_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=self.department.pk,
            quantity=2,
            reason="Testing cancellation rollback",
        )

        # Complete both approval stages.
        decide_request(
            approver=self.approver,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        decide_request(
            approver=self.custodian,
            request_id=resource_request.pk,
            stage=RequestApproval.Stage.SOURCE,
            decision=RequestApproval.Decision.APPROVED,
        )

        reservation = Reservation.objects.get(
            request=resource_request
        )

        # Simulate a database save failure after stock changes.
        with patch.object(
            Reservation,
            "save",
            side_effect=RuntimeError("Simulated save failure"),
        ):
            with self.assertRaises(RuntimeError):
                cancel_approved_reservation(
                    actor=self.requester,
                    reservation_id=reservation.pk,
                    reason="Testing rollback",
                )

        reservation.refresh_from_db()
        resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        # Reservation and request must remain approved.
        self.assertEqual(
            reservation.status,
            Reservation.Status.APPROVED,
        )
        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.APPROVED,
        )
        self.assertEqual(reservation.cancellation_reason, "")

        # Held stock must NOT be released.
        self.assertEqual(self.asset.stock.free, 3)
        self.assertEqual(self.asset.stock.held, 2)
        self.assertEqual(self.asset.stock.blocked, 0)
        self.assertEqual(self.asset.stock.total, 5)
