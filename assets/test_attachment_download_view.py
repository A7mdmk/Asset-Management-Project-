
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class AttachmentDownloadViewTests(TestCase):

    def setUp(self):
        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )

        self.custodian = User.objects.create_user(
            username="download_custodian",
            password="testpass123",
        )
        self.custodian.groups.add(group)

        self.other_custodian = User.objects.create_user(
            username="download_other",
            password="testpass123",
        )
        self.other_custodian.groups.add(group)

        self.requester = User.objects.create_user(
            username="download_requester",
            password="testpass123",
        )

        self.admin = User.objects.create_superuser(
            username="download_admin",
            password="testpass123",
            email="admin@example.com",
        )

        self.attachment_id = 1

        self.url = reverse(
            "asset_attachment_download",
            args=[self.attachment_id],
        )

    def make_attachment(self):
        file = SimpleNamespace(
            name="asset_attachments/manual.pdf",
            open=lambda mode: BytesIO(b"%PDF-1.4\nTest"),
        )

        asset = SimpleNamespace(
            custodian_id=self.custodian.pk,
        )

        return SimpleNamespace(
            pk=self.attachment_id,
            asset=asset,
            file=file,
        )

    def test_anonymous_user_redirected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_missing_attachment_returns_404(self):
        self.client.force_login(self.custodian)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    @patch("assets.views.get_object_or_404")
    def test_requester_forbidden(self, mocked_get):
        self.client.force_login(self.requester)

        mocked_get.return_value = self.make_attachment()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    @patch("assets.views.get_object_or_404")
    def test_other_custodian_forbidden(self, mocked_get):
        self.client.force_login(self.other_custodian)

        mocked_get.return_value = self.make_attachment()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    @patch("assets.views.get_object_or_404")
    def test_assigned_custodian_can_download(self, mocked_get):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_attachment()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)

        content = b"".join(response.streaming_content)

        self.assertEqual(
            content,
            b"%PDF-1.4\nTest",
        )


    @patch("assets.views.get_object_or_404")
    def test_superuser_can_download(self, mocked_get):
        self.client.force_login(self.admin)

        mocked_get.return_value = self.make_attachment()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    @patch("assets.views.get_object_or_404")
    def test_download_is_attachment(self, mocked_get):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_attachment()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertIn(
            "attachment;",
            response["Content-Disposition"],
        )

        self.assertIn(
            "manual.pdf",
            response["Content-Disposition"],
        )


    @patch("assets.views.get_object_or_404")
    def test_missing_physical_file_returns_404(
        self,
        mocked_get,
    ):
        self.client.force_login(self.custodian)

        attachment = self.make_attachment()

        def missing_file(mode):
            raise FileNotFoundError("File is missing")

        attachment.file.open = missing_file
        mocked_get.return_value = attachment

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    @patch("assets.views.get_object_or_404")
    def test_empty_file_reference_returns_404(
        self,
        mocked_get,
    ):
        self.client.force_login(self.custodian)

        attachment = self.make_attachment()
        attachment.file = None

        mocked_get.return_value = attachment

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    @patch("assets.views.get_object_or_404")
    def test_download_content_type_is_binary(
        self,
        mocked_get,
    ):
        self.client.force_login(self.custodian)

        mocked_get.return_value = self.make_attachment()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response["Content-Type"],
            "application/octet-stream",
        )

