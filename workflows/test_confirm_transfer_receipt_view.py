
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import DepartmentApprover
from assets.models import Department


User = get_user_model()


class ConfirmTransferReceiptViewTests(TestCase):

    def setUp(self):
        group, _ = Group.objects.get_or_create(
            name="Approver/Admin"
        )

        self.approver = User.objects.create_user(
            username="receipt_approver",
            password="testpass123",
        )
        self.approver.groups.add(group)

        self.other_approver = User.objects.create_user(
            username="receipt_other",
            password="testpass123",
        )
        self.other_approver.groups.add(group)

        self.requester = User.objects.create_user(
            username="receipt_requester",
            password="testpass123",
        )

        self.department = Department.objects.create(
            name="Receipt Test Department",
            code="RCPT",
        )

        self.assignment = DepartmentApprover.objects.create(
            user=self.approver,
            department=self.department,
            is_active=True,
        )

        self.transfer_id = 1

        self.url = reverse(
            "confirm_transfer_receipt",
            args=[self.transfer_id],
        )

    def make_transfer(self):
        resource_request = SimpleNamespace(
            destination_department=self.department,
        )

        reservation = SimpleNamespace(
            request=resource_request,
        )

        return SimpleNamespace(
            pk=self.transfer_id,
            reservation=reservation,
        )

    def test_anonymous_user_redirected(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)

    def test_non_approver_forbidden(self):
        self.client.force_login(self.requester)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)

    @patch("workflows.views.confirm_transfer_receipt")
    def test_get_does_not_confirm_receipt(
        self,
        mocked_service,
    ):
        self.client.force_login(self.approver)

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            reverse("incoming_transfers"),
            fetch_redirect_response=False,
        )
        mocked_service.assert_not_called()

    def test_missing_transfer_returns_404(self):
        self.client.force_login(self.approver)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 404)

    @patch("workflows.views.confirm_transfer_receipt")
    @patch("workflows.views.get_object_or_404")
    def test_unauthorized_department_forbidden(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.other_approver)

        mocked_get.return_value = self.make_transfer()

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        mocked_service.assert_not_called()

    @patch("workflows.views.confirm_transfer_receipt")
    @patch("workflows.views.get_object_or_404")
    def test_inactive_assignment_forbidden(
        self,
        mocked_get,
        mocked_service,
    ):
        self.assignment.is_active = False
        self.assignment.save()

        self.client.force_login(self.approver)

        mocked_get.return_value = self.make_transfer()

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        mocked_service.assert_not_called()

    @patch("workflows.views.confirm_transfer_receipt")
    @patch("workflows.views.get_object_or_404")
    def test_valid_post_calls_service(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.approver)

        mocked_get.return_value = self.make_transfer()

        response = self.client.post(self.url)

        self.assertRedirects(
            response,
            reverse("incoming_transfers"),
            fetch_redirect_response=False,
        )

        mocked_service.assert_called_once_with(
            actor=self.approver,
            transfer_id=self.transfer_id,
        )

    @patch("workflows.views.confirm_transfer_receipt")
    @patch("workflows.views.get_object_or_404")
    def test_validation_error_returns_400(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.approver)

        mocked_get.return_value = self.make_transfer()

        mocked_service.side_effect = ValidationError(
            "Only dispatched transfers can be received."
        )

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 400)

        self.assertContains(
            response,
            "Only dispatched transfers can be received.",
            status_code=400,
        )
