
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class InspectionRequestViewTests(TestCase):

    def setUp(self):
        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian = User.objects.create_user(
            username="inspection_custodian",
            password="testpass123",
        )
        self.custodian.groups.add(group)

        self.other_custodian = User.objects.create_user(
            username="inspection_other",
            password="testpass123",
        )
        self.other_custodian.groups.add(group)

        self.requester = User.objects.create_user(
            username="inspection_requester",
            password="testpass123",
        )

        self.asset_id = uuid.uuid4()

        self.url = reverse(
            "inspection_request",
            args=[self.asset_id],
        )

    def make_asset(self):
        return SimpleNamespace(
            pk=self.asset_id,
            custodian_id=self.custodian.pk,
            name="Inspection Test Laptop",
            department=SimpleNamespace(
                name="Engineering",
            ),
            quantity=5,
            get_tracking_mode_display=lambda: "Lot",
        )

    def test_anonymous_user_redirected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_non_custodian_forbidden(self):
        self.client.force_login(self.requester)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_missing_asset_returns_404(self):
        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    @patch("assets.views.get_object_or_404")
    def test_other_custodian_forbidden(self, mocked_get):
        self.client.force_login(self.other_custodian)
        mocked_get.return_value = self.make_asset()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    @patch("assets.views.get_object_or_404")
    def test_get_displays_request_form(self, mocked_get):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_asset()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "assets/inspection_request.html",
        )

        self.assertContains(
            response,
            "Inspection Test Laptop",
        )

    @patch("assets.views.request_asset_inspection")
    @patch("assets.views.get_object_or_404")
    def test_valid_post_calls_service(
        self, mocked_get, mocked_service
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_asset()

        response = self.client.post(
            self.url,
            {"quantity": "2"},
        )

        self.assertRedirects(
            response,
            reverse("inspection_management"),
            fetch_redirect_response=False,
        )

        mocked_service.assert_called_once_with(
            actor=self.custodian,
            asset_id=self.asset_id,
            quantity=2,
        )

    @patch("assets.views.request_asset_inspection")
    @patch("assets.views.get_object_or_404")
    def test_invalid_quantity_rejected(
        self, mocked_get, mocked_service
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_asset()

        response = self.client.post(
            self.url,
            {"quantity": "0"},
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Ensure this value is greater than or equal to 1.",
        )

        mocked_service.assert_not_called()

    @patch("assets.views.request_asset_inspection")
    @patch("assets.views.get_object_or_404")
    def test_service_validation_error_displayed(
        self, mocked_get, mocked_service
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_asset()

        mocked_service.side_effect = ValidationError(
            "Inspection quantity exceeds asset quantity."
        )

        response = self.client.post(
            self.url,
            {"quantity": "6"},
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Inspection quantity exceeds asset quantity.",
        )
