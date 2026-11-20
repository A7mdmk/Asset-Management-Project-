
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, override_settings

from .models import (
    Asset,
    AssetAttachment,
    AssetSpecification,
    Category,
    Department,
)
from .services import (
    register_asset,
    add_asset_specification,
    update_asset_specification,
    delete_asset_specification,
    add_asset_attachment,
    update_asset_attachment,
    delete_asset_attachment,
)


class AssetMetadataServiceTests(TestCase):

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)

        media_settings = override_settings(
            MEDIA_ROOT=self.temp_directory.name
        )
        media_settings.enable()
        self.addCleanup(media_settings.disable)

        User = get_user_model()

        self.department = Department.objects.create(
            name="Metadata Services Department",
            code="META-SVC",
        )

        self.category = Category.objects.create(
            name="Metadata Services Equipment",
        )

        self.custodian = User.objects.create_user(
            username="metadata_service_custodian",
            password="TestPassword123!",
        )

        self.other_user = User.objects.create_user(
            username="metadata_service_other",
            password="TestPassword123!",
        )

        self.admin = User.objects.create_superuser(
            username="metadata_service_admin",
            email="metadata_admin@example.com",
            password="TestPassword123!",
        )

        group, _ = Group.objects.get_or_create(
            name="Custodian"
        )
        self.custodian.groups.add(group)

        self.asset = register_asset(
            name="Metadata Service Laptop",
            asset_tag="META-SVC-001",
            description="Test laptop",
            category=self.category,
            department=self.department,
            custodian=self.custodian,
            location="Computer Lab",
            tracking_mode=Asset.TrackingMode.INDIVIDUAL,
            quantity=1,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.DRAFT,
        )

    def make_file(
        self,
        filename="manual.pdf",
        content=None,
    ):
        if content is None:
            content = b"%PDF-1.4\nTest PDF content"

        return SimpleUploadedFile(
            filename,
            content,
            content_type="application/octet-stream",
        )

    def create_specification(self):
        return add_asset_specification(
            actor=self.custodian,
            asset_id=self.asset.pk,
            name="RAM",
            value="16 GB",
        )

    def create_attachment(self):
        return add_asset_attachment(
            actor=self.custodian,
            asset_id=self.asset.pk,
            title="Laptop Manual",
            attachment_type=(
                AssetAttachment.AttachmentType.MANUAL
            ),
            uploaded_file=self.make_file(),
        )

    # TEST 1: ADD SPECIFICATION

    def test_add_specification(self):
        specification = self.create_specification()

        self.assertEqual(specification.name, "RAM")
        self.assertEqual(specification.value, "16 GB")
        self.assertEqual(
            self.asset.specifications.count(),
            1,
        )

    # TEST 2: UPDATE SPECIFICATION

    def test_update_specification(self):
        specification = self.create_specification()

        updated = update_asset_specification(
            actor=self.custodian,
            specification_id=specification.pk,
            name="Memory",
            value="32 GB",
        )

        self.assertEqual(updated.name, "Memory")
        self.assertEqual(updated.value, "32 GB")

    # TEST 3: DELETE SPECIFICATION

    def test_delete_specification(self):
        specification = self.create_specification()

        delete_asset_specification(
            actor=self.custodian,
            specification_id=specification.pk,
        )

        self.assertFalse(
            AssetSpecification.objects.filter(
                pk=specification.pk
            ).exists()
        )

    # TEST 4: UNAUTHORIZED SPECIFICATION CREATION

    def test_unauthorized_user_cannot_add_specification(self):
        with self.assertRaises(ValidationError):
            add_asset_specification(
                actor=self.other_user,
                asset_id=self.asset.pk,
                name="Storage",
                value="512 GB",
            )

        self.assertEqual(
            self.asset.specifications.count(),
            0,
        )

    # TEST 5: CUSTODIAN ROLE REQUIRED

    def test_specification_requires_custodian_role(self):
        self.custodian.groups.clear()

        with self.assertRaises(ValidationError):
            self.create_specification()

        self.assertEqual(
            self.asset.specifications.count(),
            0,
        )

    # TEST 6: SUPERUSER AUTHORIZATION

    def test_superuser_can_add_specification(self):
        specification = add_asset_specification(
            actor=self.admin,
            asset_id=self.asset.pk,
            name="Processor",
            value="Intel Core i7",
        )

        self.assertEqual(
            specification.value,
            "Intel Core i7",
        )

    # TEST 7: DUPLICATE SPECIFICATIONS REJECTED

    def test_duplicate_specification_rejected(self):
        self.create_specification()

        with self.assertRaises(ValidationError):
            self.create_specification()

        self.assertEqual(
            self.asset.specifications.count(),
            1,
        )

    # TEST 8: BLANK SPECIFICATION REJECTED

    def test_blank_specification_rejected(self):
        with self.assertRaises(ValidationError):
            add_asset_specification(
                actor=self.custodian,
                asset_id=self.asset.pk,
                name="   ",
                value="16 GB",
            )

    # TEST 9: VALID PDF UPLOAD

    def test_valid_pdf_upload(self):
        attachment = self.create_attachment()

        self.assertTrue(
            AssetAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )
        self.assertTrue(
            attachment.file.storage.exists(
                attachment.file.name
            )
        )

    # TEST 10: VALID IMAGE UPLOADS

    def test_valid_image_uploads(self):
        images = [
            (
                "photo.jpg",
                b"\xff\xd8\xff" + b"JPEG test content",
            ),
            (
                "photo.jpeg",
                b"\xff\xd8\xff" + b"JPEG test content",
            ),
            (
                "photo.png",
                b"\x89PNG\r\n\x1a\n" + b"PNG test content",
            ),
        ]

        for filename, content in images:
            with self.subTest(filename=filename):
                attachment = add_asset_attachment(
                    actor=self.custodian,
                    asset_id=self.asset.pk,
                    title=filename,
                    attachment_type=(
                        AssetAttachment.AttachmentType.IMAGE
                    ),
                    uploaded_file=self.make_file(
                        filename,
                        content,
                    ),
                )

                self.assertTrue(
                    attachment.file.storage.exists(
                        attachment.file.name
                    )
                )

    # TEST 11: INVALID EXTENSION

    def test_invalid_extension_rejected(self):
        with self.assertRaises(ValidationError):
            add_asset_attachment(
                actor=self.custodian,
                asset_id=self.asset.pk,
                title="Invalid Script",
                attachment_type=(
                    AssetAttachment.AttachmentType.OTHER
                ),
                uploaded_file=self.make_file(
                    "script.exe",
                    b"invalid content",
                ),
            )

    # TEST 12: FILE SIGNATURE MISMATCH

    def test_fake_pdf_rejected(self):
        with self.assertRaises(ValidationError):
            add_asset_attachment(
                actor=self.custodian,
                asset_id=self.asset.pk,
                title="Fake PDF",
                attachment_type=(
                    AssetAttachment.AttachmentType.MANUAL
                ),
                uploaded_file=self.make_file(
                    "fake.pdf",
                    b"This is not a PDF",
                ),
            )

        self.assertEqual(
            self.asset.attachments.count(),
            0,
        )

    # TEST 13: FILE SIZE LIMIT

    def test_oversized_attachment_rejected(self):
        oversized_content = (
            b"%PDF-1.4\n"
            + b"A" * (10 * 1024 * 1024)
        )

        with self.assertRaises(ValidationError):
            add_asset_attachment(
                actor=self.custodian,
                asset_id=self.asset.pk,
                title="Large Manual",
                attachment_type=(
                    AssetAttachment.AttachmentType.MANUAL
                ),
                uploaded_file=self.make_file(
                    "large.pdf",
                    oversized_content,
                ),
            )

    # TEST 14: UNAUTHORIZED UPLOAD

    def test_unauthorized_user_cannot_upload(self):
        with self.assertRaises(ValidationError):
            add_asset_attachment(
                actor=self.other_user,
                asset_id=self.asset.pk,
                title="Unauthorized File",
                attachment_type=(
                    AssetAttachment.AttachmentType.MANUAL
                ),
                uploaded_file=self.make_file(),
            )

        self.assertEqual(
            self.asset.attachments.count(),
            0,
        )

    # TEST 15: UPDATE ATTACHMENT METADATA

    def test_update_attachment_metadata(self):
        attachment = self.create_attachment()
        original_file_name = attachment.file.name

        updated = update_asset_attachment(
            actor=self.custodian,
            attachment_id=attachment.pk,
            title="Updated Manual",
            attachment_type=(
                AssetAttachment.AttachmentType.REPORT
            ),
        )

        self.assertEqual(
            updated.title,
            "Updated Manual",
        )
        self.assertEqual(
            updated.attachment_type,
            AssetAttachment.AttachmentType.REPORT,
        )
        self.assertEqual(
            updated.file.name,
            original_file_name,
        )

    # TEST 16: UNAUTHORIZED UPDATE AND DELETE

    def test_unauthorized_user_cannot_modify_attachment(self):
        attachment = self.create_attachment()

        with self.assertRaises(ValidationError):
            update_asset_attachment(
                actor=self.other_user,
                attachment_id=attachment.pk,
                title="Unauthorized Change",
            )

        with self.assertRaises(ValidationError):
            delete_asset_attachment(
                actor=self.other_user,
                attachment_id=attachment.pk,
            )

        attachment.refresh_from_db()

        self.assertEqual(
            attachment.title,
            "Laptop Manual",
        )
        self.assertTrue(
            attachment.file.storage.exists(
                attachment.file.name
            )
        )

    # TEST 17: DELETE FILE AFTER COMMIT

    def test_delete_attachment_removes_file_after_commit(self):
        attachment = self.create_attachment()

        storage = attachment.file.storage
        file_name = attachment.file.name
        attachment_id = attachment.pk

        with self.captureOnCommitCallbacks(
            execute=True
        ) as callbacks:
            delete_asset_attachment(
                actor=self.custodian,
                attachment_id=attachment_id,
            )

            self.assertFalse(
                AssetAttachment.objects.filter(
                    pk=attachment_id
                ).exists()
            )

            # Physical file should remain until commit.
            self.assertTrue(
                storage.exists(file_name)
            )

        self.assertEqual(len(callbacks), 1)
        self.assertFalse(storage.exists(file_name))

    # TEST 18: ROLLBACK PRESERVES FILE

    def test_delete_rollback_preserves_attachment(self):
        attachment = self.create_attachment()

        storage = attachment.file.storage
        file_name = attachment.file.name
        attachment_id = attachment.pk

        with self.captureOnCommitCallbacks(
            execute=True
        ) as callbacks:
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    delete_asset_attachment(
                        actor=self.custodian,
                        attachment_id=attachment_id,
                    )

                    raise RuntimeError(
                        "Simulated transaction failure"
                    )

        self.assertEqual(len(callbacks), 0)

        self.assertTrue(
            AssetAttachment.objects.filter(
                pk=attachment_id
            ).exists()
        )
        self.assertTrue(storage.exists(file_name))

    # TEST 19: INACTIVE USER REJECTED

    def test_inactive_custodian_cannot_manage_metadata(self):
        self.custodian.is_active = False
        self.custodian.save(
            update_fields=["is_active"]
        )

        with self.assertRaises(ValidationError):
            self.create_specification()

        with self.assertRaises(ValidationError):
            self.create_attachment()

        self.assertEqual(
            self.asset.specifications.count(),
            0,
        )
        self.assertEqual(
            self.asset.attachments.count(),
            0,
        )

    # TEST 20: STOCK PRESERVED

    def test_metadata_operations_preserve_stock(self):
        specification = self.create_specification()
        attachment = self.create_attachment()

        update_asset_specification(
            actor=self.custodian,
            specification_id=specification.pk,
            value="32 GB",
        )

        update_asset_attachment(
            actor=self.custodian,
            attachment_id=attachment.pk,
            title="Updated Laptop Manual",
        )

        delete_asset_specification(
            actor=self.custodian,
            specification_id=specification.pk,
        )

        with self.captureOnCommitCallbacks(
            execute=True
        ):
            delete_asset_attachment(
                actor=self.custodian,
                attachment_id=attachment.pk,
            )

        self.asset.stock.refresh_from_db()

        self.assertEqual(self.asset.stock.free, 1)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.in_transit, 0)
        self.assertEqual(self.asset.stock.in_use, 0)
        self.assertEqual(self.asset.stock.blocked, 0)
        self.assertEqual(self.asset.stock.retired, 0)
        self.assertEqual(self.asset.stock.total, 1)

    # TEST 21: FAILED SAVE CLEANS UP UPLOADED FILE

    def test_failed_attachment_save_cleans_up_file(self):
        from unittest.mock import patch

        original_save = AssetAttachment.save

        def failing_save(instance, *args, **kwargs):
            # Save the physical file and database row,
            # then simulate a failure.
            original_save(instance, *args, **kwargs)

            raise RuntimeError(
                "Simulated attachment save failure"
            )

        with patch.object(
            AssetAttachment,
            "save",
            failing_save,
        ):
            with self.assertRaises(RuntimeError):
                add_asset_attachment(
                    actor=self.custodian,
                    asset_id=self.asset.pk,
                    title="Failed Upload",
                    attachment_type=(
                        AssetAttachment.AttachmentType.MANUAL
                    ),
                    uploaded_file=self.make_file(
                        "failed_upload.pdf"
                    ),
                )

        # The transaction must roll back the row.
        self.assertEqual(
            AssetAttachment.objects.count(),
            0,
        )

        # No physical attachment file should remain.
        import os

        attachment_directory = os.path.join(
            self.temp_directory.name,
            "asset_attachments",
        )

        remaining_files = []

        if os.path.exists(attachment_directory):
            remaining_files = os.listdir(
                attachment_directory
            )

        self.assertEqual(remaining_files, [])
