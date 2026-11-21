
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.models import DepartmentApprover
from assets.models import Asset, Category, Department
from workflows.models import (
    RequestApproval,
    Reservation,
    ResourceRequest,
    Transfer,
)


User = get_user_model()


class IncomingTransfersViewTests(TestCase):

    def setUp(self):
        approver_group, _ = Group.objects.get_or_create(
            name="Approver/Admin"
        )

        self.approver = User.objects.create_user(
            username="incoming_approver",
            password="testpass123",
        )
        self.approver.groups.add(approver_group)

        self.requester = User.objects.create_user(
            username="incoming_requester",
            password="testpass123",
        )

        self.custodian = User.objects.create_user(
            username="incoming_custodian",
            password="testpass123",
        )

        self.department_a = Department.objects.create(
            name="Incoming Department A",
            code="INCA",
        )

        self.department_b = Department.objects.create(
            name="Incoming Department B",
            code="INCB",
        )

        self.assignment = DepartmentApprover.objects.create(
            department=self.department_a,
            user=self.approver,
            is_active=True,
        )

        self.category = Category.objects.create(
            name="Incoming Test Category"
        )

        self.transfer_a = self.create_transfer(
            department=self.department_a,
            name="Authorized Department Asset",
            status=Transfer.Status.DISPATCHED,
        )

        self.transfer_b = self.create_transfer(
            department=self.department_b,
            name="Other Department Asset",
            status=Transfer.Status.ARRANGED,
        )

        self.url = reverse("incoming_transfers")

    def create_transfer(self, department, name, status):
        asset = Asset.objects.create(
            name=name,
            category=self.category,
            department=department,
            custodian=self.custodian,
            location="Test Storage",
            quantity=1,
        )

        resource_request = ResourceRequest.objects.create(
            asset=asset,
            requester=self.requester,
            destination_department=department,
            quantity=1,
            reason="Incoming transfer test",
            status=ResourceRequest.Status.APPROVED,
        )

        approval = RequestApproval.objects.create(
            request=resource_request,
            approver=self.approver,
            stage=RequestApproval.Stage.SOURCE,
            decision=RequestApproval.Decision.APPROVED,
        )

        reservation = Reservation.objects.create(
            request=resource_request,
            source_approval=approval,
            quantity=1,
            status=Reservation.Status.CONVERTED,
        )

        return Transfer.objects.create(
            reservation=reservation,
            arranged_by=self.custodian,
            quantity=1,
            status=status,
        )

    def test_anonymous_user_redirected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_non_approver_forbidden(self):
        self.client.force_login(self.requester)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_authorized_approver_can_open_page(self):
        self.client.force_login(self.approver)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "workflows/incoming_transfers.html",
        )

    def test_only_authorized_department_visible(self):
        self.client.force_login(self.approver)

        response = self.client.get(self.url)

        self.assertContains(
            response,
            "Authorized Department Asset",
        )
        self.assertNotContains(
            response,
            "Other Department Asset",
        )

        self.assertEqual(
            response.context["total_transfers"],
            1,
        )

    def test_inactive_assignment_cannot_see_transfers(self):
        self.assignment.is_active = False
        self.assignment.save()

        self.client.force_login(self.approver)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["total_transfers"],
            0,
        )

    def test_inactive_department_not_visible(self):
        self.department_a.is_active = False
        self.department_a.save()

        self.client.force_login(self.approver)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["total_transfers"],
            0,
        )

    def test_status_filter(self):
        self.client.force_login(self.approver)

        response = self.client.get(
            self.url,
            {"status": Transfer.Status.ARRANGED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["total_transfers"],
            0,
        )

        response = self.client.get(
            self.url,
            {"status": Transfer.Status.DISPATCHED},
        )

        self.assertEqual(
            response.context["total_transfers"],
            1,
        )

    def test_invalid_status_filter_is_ignored(self):
        self.client.force_login(self.approver)

        response = self.client.get(
            self.url,
            {"status": "UnknownStatus"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["selected_status"],
            "",
        )
        self.assertEqual(
            response.context["total_transfers"],
            1,
        )
