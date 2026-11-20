
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import (
    Asset,
    AssetAttachment,
    AssetSpecification,
    Category,
    Department,
)
from .services import register_asset


class AssetMetadataTests(TestCase):

    def setUp(self):
        self.department = Department.objects.create(
            name="Metadata Test Department",
            code="META-TEST",
        )

        self.category = Category.objects.create(
            name="Metadata Test Equipment",
        )

        self.custodian = get_user_model().objects.create_user(
            username="metadata_custodian",
            password="TestPassword123!",
        )

        self.asset = register_asset(
            name="Dell Laptop",
            asset_tag="META-001",
            description="Laptop for student programming",
            category=self.category,
            department=self.department,
            custodian=self.custodian,
            location="Computer Science Lab",
            tracking_mode=Asset.TrackingMode.INDIVIDUAL,
            quantity=1,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.PUBLISHED,
        )

    def make_file(
        self,
        filename="manual.pdf",
        size=100,
    ):
        return SimpleUploadedFile(
            filename,
            b"A" * size,
            content_type="application/pdf",
        )

    # TEST 1: CREATE SPECIFICATION

    def test_create_asset_specification(self):
        specification = AssetSpecification(
            asset=self.asset,
            name="RAM",
            value="16 GB",
        )

        specification.full_clean()
        specification.save()

        self.assertEqual(
            self.asset.specifications.count(),
            1,
        )
        self.assertEqual(specification.value, "16 GB")

    # TEST 2: MULTIPLE SPECIFICATIONS

    def test_asset_supports_multiple_specifications(self):
        for name, value in [
            ("RAM", "16 GB"),
            ("Storage", "512 GB SSD"),
            ("Processor", "Intel Core i7"),
        ]:
            specification = AssetSpecification(
                asset=self.asset,
                name=name,
                value=value,
            )
            specification.full_clean()
            specification.save()

        self.assertEqual(
            self.asset.specifications.count(),
            3,
        )

    # TEST 3: DUPLICATE SPECIFICATION NAME

    def test_duplicate_specification_name_is_rejected(self):
        AssetSpecification.objects.create(
            asset=self.asset,
            name="RAM",
            value="16 GB",
        )

        duplicate = AssetSpecification(
            asset=self.asset,
            name="RAM",
            value="32 GB",
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    # TEST 4: EMPTY SPECIFICATION NAME

    def test_empty_specification_name_is_rejected(self):
        specification = AssetSpecification(
            asset=self.asset,
            name="   ",
            value="16 GB",
        )

        with self.assertRaises(ValidationError):
            specification.full_clean()

    # TEST 5: EMPTY SPECIFICATION VALUE

    def test_empty_specification_value_is_rejected(self):
        specification = AssetSpecification(
            asset=self.asset,
            name="RAM",
            value="   ",
        )

        with self.assertRaises(ValidationError):
            specification.full_clean()

    # TEST 6: VALID PDF ATTACHMENT

    def test_valid_pdf_attachment_passes_validation(self):
        attachment = AssetAttachment(
            asset=self.asset,
            title="Equipment Manual",
            attachment_type=AssetAttachment.AttachmentType.MANUAL,
            file=self.make_file(),
        )

        attachment.full_clean()

        self.assertEqual(
            attachment.attachment_type,
            AssetAttachment.AttachmentType.MANUAL,
        )

    # TEST 7: VALID IMAGE ATTACHMENTS

    def test_valid_image_extensions(self):
        for filename in ("photo.jpg", "photo.jpeg", "photo.png"):
            with self.subTest(filename=filename):
                attachment = AssetAttachment(
                    asset=self.asset,
                    title="Equipment Photo",
                    attachment_type=(
                        AssetAttachment.AttachmentType.IMAGE
                    ),
                    file=self.make_file(filename=filename),
                )

                attachment.full_clean()

    # TEST 8: INVALID FILE EXTENSION

    def test_invalid_file_extension_is_rejected(self):
        attachment = AssetAttachment(
            asset=self.asset,
            title="Invalid File",
            file=self.make_file(filename="script.exe"),
        )

        with self.assertRaises(ValidationError):
            attachment.full_clean()

    # TEST 9: OVERSIZED ATTACHMENT

    def test_attachment_exceeding_10mb_is_rejected(self):
        attachment = AssetAttachment(
            asset=self.asset,
            title="Oversized Manual",
            file=self.make_file(
                size=10 * 1024 * 1024 + 1,
            ),
        )

        with self.assertRaises(ValidationError):
            attachment.full_clean()

    # TEST 10: EMPTY ATTACHMENT TITLE

    def test_empty_attachment_title_is_rejected(self):
        attachment = AssetAttachment(
            asset=self.asset,
            title="   ",
            file=self.make_file(),
        )

        with self.assertRaises(ValidationError):
            attachment.full_clean()

    # TEST 11: INVALID ATTACHMENT TYPE

    def test_invalid_attachment_type_is_rejected(self):
        attachment = AssetAttachment(
            asset=self.asset,
            title="Equipment Manual",
            attachment_type="Unknown",
            file=self.make_file(),
        )

        with self.assertRaises(ValidationError):
            attachment.full_clean()

    # TEST 12: METADATA DOES NOT MODIFY STOCK

    def test_specifications_and_attachments_preserve_stock(self):
        specification = AssetSpecification(
            asset=self.asset,
            name="Storage",
            value="512 GB SSD",
        )

        specification.full_clean()
        specification.save()

        attachment = AssetAttachment(
            asset=self.asset,
            title="Equipment Manual",
            file=self.make_file(),
        )

        attachment.full_clean()

        self.asset.stock.refresh_from_db()

        self.assertEqual(self.asset.stock.free, 1)
        self.assertEqual(self.asset.stock.held, 0)
        self.assertEqual(self.asset.stock.in_transit, 0)
        self.assertEqual(self.asset.stock.total, 1)
