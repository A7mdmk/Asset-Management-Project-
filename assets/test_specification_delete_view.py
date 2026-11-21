
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class SpecificationDeleteViewTests(TestCase):

    def setUp(self):
        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian = User.objects.create_user(
            username="spec_delete_custodian",
            password="testpass123",
        )
        self.custodian.groups.add(group)

        self.other_custodian = User.objects.create_user(
            username="spec_delete_other",
            password="testpass123",
        )
        self.other_custodian.groups.add(group)

        self.requester = User.objects.create_user(
            username="spec_delete_requester",
            password="testpass123",
        )

        self.asset_id = uuid4()
        self.specification_id = 1

        self.url = reverse(
            "asset_specification_delete",
            args=[self.specification_id],
        )

    def make_specification(self):
        asset = SimpleNamespace(
            pk=self.asset_id,
            custodian_id=self.custodian.pk,
            name="Test Laptop",
            department=SimpleNamespace(
                name="Engineering",
            ),
        )

        return SimpleNamespace(
            pk=self.specification_id,
            asset=asset,
            name="RAM",
            value="16 GB",
        )

    def test_anonymous_user_redirected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_non_custodian_forbidden(self):
        self.client.force_login(self.requester)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_missing_specification_returns_404(self):
        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    @patch("assets.views.get_object_or_404")
    def test_other_custodian_forbidden(self, mocked_get):
        self.client.force_login(self.other_custodian)

        mocked_get.return_value = self.make_specification()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    @patch("assets.views.get_object_or_404")
    def test_get_displays_confirmation_page(self, mocked_get):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_specification()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "assets/specification_delete.html",
        )

        self.assertContains(response, "Test Laptop")
        self.assertContains(response, "RAM")
        self.assertContains(response, "16 GB")

    @patch("assets.views.delete_asset_specification")
    @patch("assets.views.get_object_or_404")
    def test_get_does_not_delete(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_specification()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        service.assert_not_called()

    @patch("assets.views.delete_asset_specification")
    @patch("assets.views.get_object_or_404")
    def test_post_calls_delete_service(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_specification()

        response = self.client.post(self.url)

        self.assertRedirects(
            response,
            reverse(
                "asset_metadata",
                args=[self.asset_id],
            ),
            fetch_redirect_response=False,
        )

        service.assert_called_once_with(
            actor=self.custodian,
            specification_id=self.specification_id,
        )

    @patch("assets.views.delete_asset_specification")
    @patch("assets.views.get_object_or_404")
    def test_service_validation_error_displayed(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_specification()

        service.side_effect = ValidationError(
            "Specification cannot be deleted."
        )

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Specification cannot be deleted.",
        )

    @patch("assets.views.delete_asset_specification")
    @patch("assets.views.get_object_or_404")
    def test_multiple_get_requests_do_not_delete(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_specification()

        self.client.get(self.url)
        self.client.get(self.url)

        service.assert_not_called()

    @patch("assets.views.delete_asset_specification")
    @patch("assets.views.get_object_or_404")
    def test_delete_confirmation_has_csrf_form(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_specification()

        response = self.client.get(self.url)

        self.assertContains(response, 'method="post"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        service.assert_not_called()
