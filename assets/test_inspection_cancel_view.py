
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class InspectionCancelViewTests(TestCase):

    def setUp(self):
        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian = User.objects.create_user(
            username="cancel_inspection_custodian",
            password="testpass123",
        )
        self.custodian.groups.add(group)

        self.other_custodian = User.objects.create_user(
            username="cancel_inspection_other",
            password="testpass123",
        )
        self.other_custodian.groups.add(group)

        self.requester = User.objects.create_user(
            username="cancel_inspection_requester",
            password="testpass123",
        )

        self.inspection_id = 1
        self.url = reverse(
            "inspection_cancel",
            args=[self.inspection_id],
        )

    def make_inspection(self):
        asset = SimpleNamespace(
            custodian_id=self.custodian.pk,
        )

        return SimpleNamespace(
            pk=self.inspection_id,
            asset=asset,
        )

    def test_anonymous_user_redirected(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)

    def test_non_custodian_forbidden(self):
        self.client.force_login(self.requester)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)

    def test_missing_inspection_returns_404(self):
        self.client.force_login(self.custodian)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 404)

    @patch("assets.views.cancel_asset_inspection")
    @patch("assets.views.get_object_or_404")
    def test_other_custodian_forbidden(
        self, mocked_get, service
    ):
        self.client.force_login(self.other_custodian)
        mocked_get.return_value = self.make_inspection()

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        service.assert_not_called()

    @patch("assets.views.cancel_asset_inspection")
    def test_get_does_not_cancel(self, service):
        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            reverse("inspection_management"),
            fetch_redirect_response=False,
        )
        service.assert_not_called()

    @patch("assets.views.cancel_asset_inspection")
    @patch("assets.views.get_object_or_404")
    def test_valid_post_calls_service(
        self, mocked_get, service
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_inspection()

        response = self.client.post(self.url)

        self.assertRedirects(
            response,
            reverse("inspection_management"),
            fetch_redirect_response=False,
        )

        service.assert_called_once_with(
            actor=self.custodian,
            inspection_id=self.inspection_id,
        )

    @patch("assets.views.cancel_asset_inspection")
    @patch("assets.views.get_object_or_404")
    def test_validation_error_returns_400(
        self, mocked_get, service
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_inspection()

        service.side_effect = ValidationError(
            "Only pending inspections can be cancelled."
        )

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 400)

        self.assertContains(
            response,
            "Only pending inspections can be cancelled.",
            status_code=400,
        )

    @patch("assets.views.cancel_asset_inspection")
    @patch("assets.views.get_object_or_404")
    def test_service_not_called_for_wrong_custodian(
        self, mocked_get, service
    ):
        self.client.force_login(self.other_custodian)
        mocked_get.return_value = self.make_inspection()

        self.client.post(self.url)

        service.assert_not_called()
