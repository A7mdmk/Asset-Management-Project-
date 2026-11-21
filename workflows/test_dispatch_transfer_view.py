
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class DispatchTransferViewTests(TestCase):

    def setUp(self):
        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian = User.objects.create_user(
            username="dispatch_custodian",
            password="testpass123",
        )
        self.custodian.groups.add(group)

        self.other_custodian = User.objects.create_user(
            username="dispatch_other",
            password="testpass123",
        )
        self.other_custodian.groups.add(group)

        self.requester = User.objects.create_user(
            username="dispatch_requester",
            password="testpass123",
        )

        self.transfer_id = 1

        self.url = reverse(
            "dispatch_transfer",
            args=[self.transfer_id],
        )

    def make_transfer(self):
        asset = SimpleNamespace(
            custodian_id=self.custodian.pk,
        )

        resource_request = SimpleNamespace(
            asset=asset,
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

    def test_non_custodian_forbidden(self):
        self.client.force_login(self.requester)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)

    def test_missing_transfer_returns_404(self):
        self.client.force_login(self.custodian)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 404)

    @patch("workflows.views.dispatch_transfer")
    @patch("workflows.views.get_object_or_404")
    def test_other_custodian_forbidden(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.other_custodian)

        mocked_get.return_value = self.make_transfer()

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        mocked_service.assert_not_called()

    @patch("workflows.views.dispatch_transfer")
    @patch("workflows.views.get_object_or_404")
    def test_get_does_not_dispatch(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_transfer()

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            reverse("transfer_management"),
            fetch_redirect_response=False,
        )

        mocked_service.assert_not_called()

    @patch("workflows.views.dispatch_transfer")
    @patch("workflows.views.get_object_or_404")
    def test_valid_post_calls_service(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_transfer()

        response = self.client.post(self.url)

        self.assertRedirects(
            response,
            reverse("transfer_management"),
            fetch_redirect_response=False,
        )

        mocked_service.assert_called_once_with(
            actor=self.custodian,
            transfer_id=self.transfer_id,
        )

    @patch("workflows.views.dispatch_transfer")
    @patch("workflows.views.get_object_or_404")
    def test_service_validation_error_returns_400(
        self,
        mocked_get,
        mocked_service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_transfer()

        mocked_service.side_effect = ValidationError(
            "Only arranged transfers can be dispatched."
        )

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 400)

        self.assertContains(
            response,
            "Only arranged transfers can be dispatched.",
            status_code=400,
        )
