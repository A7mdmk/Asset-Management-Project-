
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class SpecificationEditViewTests(TestCase):

    def setUp(self):
        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian = User.objects.create_user(
            username="spec_edit_custodian",
            password="testpass123",
        )
        self.custodian.groups.add(group)

        self.other_custodian = User.objects.create_user(
            username="spec_edit_other",
            password="testpass123",
        )
        self.other_custodian.groups.add(group)

        self.requester = User.objects.create_user(
            username="spec_edit_requester",
            password="testpass123",
        )

        self.asset_id = uuid4()
        self.specification_id = 1

        self.url = reverse(
            "asset_specification_edit",
            args=[self.specification_id],
        )

        self.valid_data = {
            "name": "RAM",
            "value": "32 GB",
        }

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
    def test_get_displays_existing_values(self, mocked_get):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_specification()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "assets/specification_edit.html",
        )

        self.assertContains(response, "Test Laptop")
        self.assertContains(response, 'value="RAM"')
        self.assertContains(response, 'value="16 GB"')

    @patch("assets.views.update_asset_specification")
    @patch("assets.views.get_object_or_404")
    def test_get_does_not_update(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_specification()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        service.assert_not_called()

    @patch("assets.views.update_asset_specification")
    @patch("assets.views.get_object_or_404")
    def test_valid_post_calls_service(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_specification()

        response = self.client.post(
            self.url,
            self.valid_data,
        )

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
            name="RAM",
            value="32 GB",
        )

    @patch("assets.views.update_asset_specification")
    @patch("assets.views.get_object_or_404")
    def test_empty_name_rejected(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_specification()

        response = self.client.post(
            self.url,
            {
                "name": "",
                "value": "32 GB",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "This field is required.",
        )
        service.assert_not_called()

    @patch("assets.views.update_asset_specification")
    @patch("assets.views.get_object_or_404")
    def test_empty_value_rejected(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_specification()

        response = self.client.post(
            self.url,
            {
                "name": "RAM",
                "value": "",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "This field is required.",
        )
        service.assert_not_called()

    @patch("assets.views.update_asset_specification")
    @patch("assets.views.get_object_or_404")
    def test_duplicate_name_error_displayed(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_specification()

        service.side_effect = ValidationError(
            {
                "name": [
                    "Specification with this name already exists."
                ]
            }
        )

        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Specification with this name already exists.",
        )
