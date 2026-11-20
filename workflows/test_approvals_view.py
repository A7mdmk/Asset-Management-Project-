
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.models import DepartmentApprover
from assets.models import (
    Asset,
    Category,
    Department,
    StockBalance,
)
from .models import (
    RequestApproval,
    ResourceRequest,
    Reservation,
)


class ApprovalsViewTests(TestCase):

    def setUp(self):
        User = get_user_model()

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
            username="approval_test_requester",
            password="TestPassword123!",
        )
        self.requester.groups.add(requester_group)

        self.approver = User.objects.create_user(
            username="approval_test_approver",
            password="TestPassword123!",
        )
        self.approver.groups.add(approver_group)

        self.custodian = User.objects.create_user(
            username="approval_test_custodian",
            password="TestPassword123!",
        )
        self.custodian.groups.add(custodian_group)

        self.other_user = User.objects.create_user(
            username="approval_test_other",
            password="TestPassword123!",
        )

        self.source_department = Department.objects.create(
            name="Approval Source Department",
            code="APPSRC",
            is_active=True,
        )

        self.destination_department = Department.objects.create(
            name="Approval Destination Department",
            code="APPDST",
            is_active=True,
        )

        self.category = Category.objects.create(
            name="Approval Test Equipment",
        )

        self.asset = Asset.objects.create(
            name="Approval Test Monitor",
            asset_tag="APPROVAL-TEST-001",
            category=self.category,
            department=self.source_department,
            custodian=self.custodian,
            location="Test Lab",
            tracking_mode=Asset.TrackingMode.INDIVIDUAL,
            quantity=1,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.PUBLISHED,
        )

        StockBalance.objects.create(
            asset=self.asset,
            free=1,
        )

        DepartmentApprover.objects.create(
            user=self.approver,
            department=self.destination_department,
            is_active=True,
        )

        self.resource_request = ResourceRequest.objects.create(
            asset=self.asset,
            requester=self.requester,
            destination_department=self.destination_department,
            quantity=1,
            reason="Needed for an academic project.",
        )

        self.queue_url = reverse("approvals")

        self.destination_url = reverse(
            "approval_decision",
            args=[
                self.resource_request.pk,
                RequestApproval.Stage.DESTINATION,
            ],
        )

        self.source_url = reverse(
            "approval_decision",
            args=[
                self.resource_request.pk,
                RequestApproval.Stage.SOURCE,
            ],
        )

    def approve_destination(self):
        self.client.force_login(self.approver)

        return self.client.post(
            self.destination_url,
            {
                "decision": RequestApproval.Decision.APPROVED,
                "comment": "Accepted by destination.",
            },
        )

    # TEST 1

    def test_queue_requires_login(self):
        response = self.client.get(self.queue_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    # TEST 2

    def test_non_approver_cannot_access_queue(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.queue_url)

        self.assertEqual(response.status_code, 403)

    # TEST 3

    def test_destination_approver_sees_request(self):
        self.client.force_login(self.approver)

        response = self.client.get(self.queue_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Approval Test Monitor",
        )

        self.assertEqual(
            list(response.context["destination_requests"]),
            [self.resource_request],
        )

    # TEST 4

    def test_unauthorized_user_cannot_decide(self):
        self.client.force_login(self.other_user)

        response = self.client.post(
            self.destination_url,
            {
                "decision": RequestApproval.Decision.APPROVED,
                "comment": "",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            RequestApproval.objects.filter(
                request=self.resource_request
            ).exists()
        )

    # TEST 5

    def test_destination_approval_succeeds(self):
        response = self.approve_destination()

        self.assertRedirects(
            response,
            self.queue_url,
        )

        self.assertTrue(
            RequestApproval.objects.filter(
                request=self.resource_request,
                stage=RequestApproval.Stage.DESTINATION,
                decision=RequestApproval.Decision.APPROVED,
            ).exists()
        )

        self.resource_request.refresh_from_db()

        self.assertEqual(
            self.resource_request.status,
            ResourceRequest.Status.PENDING,
        )

        self.asset.stock.refresh_from_db()

        self.assertEqual(self.asset.stock.free, 1)
        self.assertEqual(self.asset.stock.held, 0)

    # TEST 6

    def test_rejection_requires_comment(self):
        self.client.force_login(self.approver)

        response = self.client.post(
            self.destination_url,
            {
                "decision": RequestApproval.Decision.REJECTED,
                "comment": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)

        self.assertFalse(
            RequestApproval.objects.filter(
                request=self.resource_request
            ).exists()
        )

    # TEST 7

    def test_destination_rejection_succeeds(self):
        self.client.force_login(self.approver)

        response = self.client.post(
            self.destination_url,
            {
                "decision": RequestApproval.Decision.REJECTED,
                "comment": "Insufficient justification.",
            },
        )

        self.assertRedirects(
            response,
            self.queue_url,
        )

        self.resource_request.refresh_from_db()

        self.assertEqual(
            self.resource_request.status,
            ResourceRequest.Status.REJECTED,
        )

    # TEST 8

    def test_source_cannot_approve_before_destination(self):
        self.client.force_login(self.custodian)

        response = self.client.post(
            self.source_url,
            {
                "decision": RequestApproval.Decision.APPROVED,
                "comment": "",
            },
        )

        self.assertEqual(response.status_code, 403)

        self.assertFalse(
            Reservation.objects.filter(
                request=self.resource_request
            ).exists()
        )

    # TEST 9

    def test_full_two_stage_approval_reserves_stock(self):
        first_response = self.approve_destination()

        self.assertEqual(first_response.status_code, 302)

        self.client.force_login(self.custodian)

        response = self.client.post(
            self.source_url,
            {
                "decision": RequestApproval.Decision.APPROVED,
                "comment": "Approved for release.",
            },
        )

        self.assertRedirects(
            response,
            self.queue_url,
        )

        self.resource_request.refresh_from_db()
        self.asset.stock.refresh_from_db()

        self.assertEqual(
            self.resource_request.status,
            ResourceRequest.Status.APPROVED,
        )

        self.assertEqual(self.asset.stock.free, 0)
        self.assertEqual(self.asset.stock.held, 1)

        self.assertTrue(
            Reservation.objects.filter(
                request=self.resource_request
            ).exists()
        )

        self.assertEqual(
            RequestApproval.objects.filter(
                request=self.resource_request
            ).count(),
            2,
        )
