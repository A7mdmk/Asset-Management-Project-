
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class AttachmentUploadViewTests(TestCase):

    def setUp(self):
        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian = User.objects.create_user(
            username="attachment_custodian",
            password="testpass123",
        )
        self.custodian.groups.add(group)

        self.other_custodian = User.objects.create_user(
            username="attachment_other",
            password="testpass123",
        )
        self.other_custodian.groups.add(group)

        self.requester = User.objects.create_user(
            username="attachment_requester",
            password="testpass123",
        )

        self.asset_id = uuid4()

        self.url = reverse(
            "asset_attachment_upload",
            args=[self.asset_id],
        )

    def make_asset(self):
        return SimpleNamespace(
            pk=self.asset_id,
            custodian_id=self.custodian.pk,
            name="Test Laptop",
            category=SimpleNamespace(
                name="Electronics",
            ),
            department=SimpleNamespace(
                name="Engineering",
            ),
        )

    def make_file(self):
        return SimpleUploadedFile(
            "manual.pdf",
            b"%PDF-1.4\nTest document",
            content_type="application/pdf",
        )

    def valid_data(self):
        return {
            "title": "Laptop Manual",
            "attachment_type": "Manual",
            "uploaded_file": self.make_file(),
        }

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
    def test_get_displays_upload_form(self, mocked_get):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_asset()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "assets/attachment_upload.html",
        )

        self.assertContains(response, "Test Laptop")
        self.assertContains(response, "Attachment Title")
        self.assertContains(response, "Attachment Type")
        self.assertContains(response, "Attachment File")

    @patch("assets.views.add_asset_attachment")
    @patch("assets.views.get_object_or_404")
    def test_get_does_not_upload(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_asset()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        service.assert_not_called()

    @patch("assets.views.add_asset_attachment")
    @patch("assets.views.get_object_or_404")
    def test_valid_post_calls_service(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_asset()

        response = self.client.post(
            self.url,
            self.valid_data(),
        )

        self.assertRedirects(
            response,
            reverse(
                "asset_metadata",
                args=[self.asset_id],
            ),
            fetch_redirect_response=False,
        )

        service.assert_called_once()

        kwargs = service.call_args.kwargs

        self.assertEqual(
            kwargs["actor"],
            self.custodian,
        )

        self.assertEqual(
            kwargs["asset_id"],
            self.asset_id,
        )

        self.assertEqual(
            kwargs["title"],
            "Laptop Manual",
        )

        self.assertEqual(
            kwargs["attachment_type"],
            "Manual",
        )

        self.assertEqual(
            kwargs["uploaded_file"].name,
            "manual.pdf",
        )

    @patch("assets.views.add_asset_attachment")
    @patch("assets.views.get_object_or_404")
    def test_empty_title_rejected(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_asset()

        data = self.valid_data()
        data["title"] = ""

        response = self.client.post(
            self.url,
            data,
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "This field is required.",
        )

        service.assert_not_called()

    @patch("assets.views.add_asset_attachment")
    @patch("assets.views.get_object_or_404")
    def test_missing_file_rejected(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_asset()

        response = self.client.post(
            self.url,
            {
                "title": "Laptop Manual",
                "attachment_type": "Manual",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "This field is required.",
        )

        service.assert_not_called()

    @patch("assets.views.add_asset_attachment")
    @patch("assets.views.get_object_or_404")
    def test_invalid_file_error_displayed(
        self,
        mocked_get,
        service,
    ):
        self.client.force_login(self.custodian)
        mocked_get.return_value = self.make_asset()

        service.side_effect = ValidationError(
            "Attachment content does not match its file extension."
        )

        response = self.client.post(
            self.url,
            self.valid_data(),
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Attachment content does not match its file extension.",
        )
