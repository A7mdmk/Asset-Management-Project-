
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from assets.models import AssetDisposition


User = get_user_model()


class DispositionCancelViewTests(TestCase):

    def setUp(self):
        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian = User.objects.create_user(
            username="cancel_disp_custodian",
            password="testpass123",
        )
        self.custodian.groups.add(group)

        self.other_custodian = User.objects.create_user(
            username="cancel_disp_other",
            password="testpass123",
        )
        self.other_custodian.groups.add(group)

        self.requester = User.objects.create_user(
            username="cancel_disp_requester",
            password="testpass123",
        )

        self.disposition_id = 1

        self.url = reverse(
            "disposition_cancel",
            args=[self.disposition_id],
        )

        self.valid_data = {
            "reason": "Asset disposition no longer required.",
        }

    def make_disposition(
        self,
        status=AssetDisposition.Status.PENDING,
    ):
        asset = SimpleNamespace(
            custodian_id=self.custodian.pk,
            name="Disposition Test Laptop",
            department=SimpleNamespace(
                name="Engineering",
            ),
        )

        return SimpleNamespace(
            pk=self.disposition_id,
            asset=asset,
            quantity=1,
            status=status,
            get_disposition_type_display=lambda: "Retired",
            get_status_display=lambda: status,
        )

    def test_anonymous_user_redirected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_non_custodian_forbidden(self):
        self.client.force_login(self.requester)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_missing_disposition_returns_404(self):
        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    @patch("assets.views.get_object_or_404")
    def test_other_custodian_forbidden(self, mocked_get):
        self.client.force_login(self.other_custodian)

        mocked_get.return_value = self.make_disposition()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    @patch("assets.views.cancel_asset_disposition")
    @patch("assets.views.get_object_or_404")
    def test_completed_disposition_redirected(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_disposition(
            status=AssetDisposition.Status.COMPLETED,
        )

        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertRedirects(
            response,
            reverse("disposition_management"),
            fetch_redirect_response=False,
        )

        service.assert_not_called()

    @patch("assets.views.get_object_or_404")
    def test_get_displays_cancellation_form(self, mocked_get):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_disposition()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "assets/disposition_cancel.html",
        )

        self.assertContains(
            response,
            "Disposition Test Laptop",
        )

    @patch("assets.views.cancel_asset_disposition")
    @patch("assets.views.get_object_or_404")
    def test_get_does_not_cancel(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_disposition()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        service.assert_not_called()

    @patch("assets.views.cancel_asset_disposition")
    @patch("assets.views.get_object_or_404")
    def test_valid_post_calls_service(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_disposition()

        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertRedirects(
            response,
            reverse("disposition_management"),
            fetch_redirect_response=False,
        )

        service.assert_called_once_with(
            actor=self.custodian,
            disposition_id=self.disposition_id,
            reason="Asset disposition no longer required.",
        )

    @patch("assets.views.cancel_asset_disposition")
    @patch("assets.views.get_object_or_404")
    def test_empty_reason_rejected(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_disposition()

        response = self.client.post(
            self.url,
            {"reason": ""},
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "This field is required.",
        )

        service.assert_not_called()

    @patch("assets.views.cancel_asset_disposition")
    @patch("assets.views.get_object_or_404")
    def test_service_validation_error_displayed(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_disposition()

        service.side_effect = ValidationError(
            "Only pending dispositions can be cancelled."
        )

        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Only pending dispositions can be cancelled.",
        )
