
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MinValueValidator,
)
from django.db import models
from django.utils import timezone


# ==========================================================
# DEPARTMENT
# ==========================================================

class Department(models.Model):
    name = models.CharField(
        max_length=120,
        unique=True,
    )

    code = models.CharField(
        max_length=20,
        unique=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    def __str__(self):
        return self.name


# ==========================================================
# CATEGORY
# ==========================================================

class Category(models.Model):
    name = models.CharField(
        max_length=120,
        unique=True,
    )

    description = models.TextField(
        blank=True,
    )

    def __str__(self):
        return self.name


# ==========================================================
# ASSET
# ==========================================================

class Asset(models.Model):

    class TrackingMode(models.TextChoices):
        INDIVIDUAL = "Individual", "Individual"
        LOT = "Lot", "Lot"

    class Condition(models.TextChoices):
        GOOD = "Good", "Good"
        FAIR = "Fair", "Fair"
        NEEDS_INSPECTION = "NeedsInspection", "Needs Inspection"
        NEEDS_REPAIR = "NeedsRepair", "Needs Repair"
        UNSAFE = "Unsafe", "Unsafe"

    class Lifecycle(models.TextChoices):
        ACTIVE = "Active", "Active"
        RETIRED = "Retired", "Retired"
        DONATED = "Donated", "Donated"
        RECYCLED = "Recycled", "Recycled"
        DISPOSED = "Disposed", "Disposed"

    class Publication(models.TextChoices):
        DRAFT = "Draft", "Draft"
        PUBLISHED = "Published", "Published"
        WITHDRAWN = "Withdrawn", "Withdrawn"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        max_length=120,
    )

    description = models.TextField(
        max_length=2000,
        blank=True,
    )

    asset_tag = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
    )

    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
    )

    location = models.CharField(
        max_length=255,
    )

    tracking_mode = models.CharField(
        max_length=20,
        choices=TrackingMode.choices,
        default=TrackingMode.INDIVIDUAL,
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    condition = models.CharField(
        max_length=20,
        choices=Condition.choices,
        default=Condition.GOOD,
    )

    lifecycle = models.CharField(
        max_length=20,
        choices=Lifecycle.choices,
        default=Lifecycle.ACTIVE,
    )

    publication = models.CharField(
        max_length=20,
        choices=Publication.choices,
        default=Publication.DRAFT,
    )

    acquisition_date = models.DateField(
        null=True,
        blank=True,
    )

    estimated_value_aed = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    mass_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def clean(self):
        super().clean()

        errors = {}

        if self.tracking_mode == self.TrackingMode.INDIVIDUAL:
            if self.quantity != 1:
                errors["quantity"] = (
                    "An individually tracked asset must have quantity 1."
                )

        if self.acquisition_date:
            if self.acquisition_date > timezone.localdate():
                errors["acquisition_date"] = (
                    "Acquisition date cannot be in the future."
                )

        if self.department_id and not self.department.is_active:
            errors["department"] = "Department must be active."

        if self.custodian_id and not self.custodian.is_active:
            errors["custodian"] = "Custodian must be active."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name


# ==========================================================
# STOCK BALANCE
# ==========================================================

class StockBalance(models.Model):

    asset = models.OneToOneField(
        Asset,
        on_delete=models.PROTECT,
        related_name="stock",
    )

    free = models.PositiveIntegerField(
        default=0,
    )

    held = models.PositiveIntegerField(
        default=0,
    )

    in_transit = models.PositiveIntegerField(
        default=0,
    )

    in_use = models.PositiveIntegerField(
        default=0,
    )

    blocked = models.PositiveIntegerField(
        default=0,
    )

    retired = models.PositiveIntegerField(
        default=0,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    @property
    def total(self):
        return (
            self.free
            + self.held
            + self.in_transit
            + self.in_use
            + self.blocked
            + self.retired
        )

    def clean(self):
        super().clean()

        if self.asset_id and self.total != self.asset.quantity:
            raise ValidationError(
                "Stock balances must equal the asset quantity."
            )

    def __str__(self):
        return f"{self.asset.name}: {self.free} available"


# ==========================================================
# ASSET SPECIFICATIONS
# ==========================================================

class AssetSpecification(models.Model):

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="specifications",
    )

    name = models.CharField(
        max_length=100,
    )

    value = models.CharField(
        max_length=500,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "name"],
                name="unique_asset_specification_name",
            ),
        ]

        ordering = ["name"]

    def clean(self):
        super().clean()

        errors = {}

        if not self.name or not self.name.strip():
            errors["name"] = (
                "Specification name is required."
            )

        if not self.value or not self.value.strip():
            errors["value"] = (
                "Specification value is required."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"{self.asset.name} - "
            f"{self.name}: {self.value}"
        )


# ==========================================================
# ASSET ATTACHMENTS
# ==========================================================

class AssetAttachment(models.Model):

    class AttachmentType(models.TextChoices):
        IMAGE = "Image", "Image"
        MANUAL = "Manual", "Manual"
        REPORT = "Report", "Report"
        OTHER = "Other", "Other"

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="attachments",
    )

    title = models.CharField(
        max_length=150,
    )

    attachment_type = models.CharField(
        max_length=20,
        choices=AttachmentType.choices,
        default=AttachmentType.OTHER,
    )

    file = models.FileField(
        upload_to="asset_attachments/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf",
                    "jpg",
                    "jpeg",
                    "png",
                ],
            ),
        ],
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
    )

    def clean(self):
        super().clean()

        errors = {}

        if not self.title or not self.title.strip():
            errors["title"] = (
                "Attachment title is required."
            )

        if self.file:
            max_size = 10 * 1024 * 1024

            if (
                self.file.size is not None
                and self.file.size > max_size
            ):
                errors["file"] = (
                    "Attachment size cannot exceed 10 MB."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"{self.asset.name} - "
            f"{self.title}"
        )

# ==========================================================
# ASSET MAINTENANCE
# ==========================================================

class AssetMaintenance(models.Model):

    class Status(models.TextChoices):
        REPORTED = "Reported", "Reported"
        IN_PROGRESS = "InProgress", "In Progress"
        COMPLETED = "Completed", "Completed"
        CANCELLED = "Cancelled", "Cancelled"

    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="maintenance_records",
    )

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reported_maintenance",
    )

    title = models.CharField(
        max_length=150,
    )

    description = models.TextField(
        max_length=2000,
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        default=1,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REPORTED,
    )

    repair_notes = models.TextField(
        max_length=2000,
        blank=True,
    )

    reported_at = models.DateTimeField(
        auto_now_add=True,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-reported_at"]

    def clean(self):
        super().clean()

        errors = {}

        if not self.title or not self.title.strip():
            errors["title"] = (
                "Maintenance title is required."
            )

        if not self.description or not self.description.strip():
            errors["description"] = (
                "Maintenance description is required."
            )

        if self.asset_id:
            if self.quantity > self.asset.quantity:
                errors["quantity"] = (
                    "Maintenance quantity cannot exceed "
                    "the asset's total quantity."
                )

            if (
                self.asset.tracking_mode
                == Asset.TrackingMode.INDIVIDUAL
                and self.quantity != 1
            ):
                errors["quantity"] = (
                    "Individual assets require "
                    "maintenance quantity 1."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"Maintenance #{self.pk} - "
            f"{self.asset.name} ({self.status})"
        )

# ==========================================================
# ASSET INSPECTION
# ==========================================================

class AssetInspection(models.Model):

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        COMPLETED = "Completed", "Completed"
        CANCELLED = "Cancelled", "Cancelled"

    class Recommendation(models.TextChoices):
        RETURN_TO_SERVICE = (
            "ReturnToService",
            "Return to Service",
        )
        REPAIR = "Repair", "Repair"
        RETIRE = "Retire", "Retire"
        DONATE = "Donate", "Donate"
        RECYCLE = "Recycle", "Recycle"
        DISPOSE = "Dispose", "Dispose"

    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="inspection_records",
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_inspections",
    )

    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="completed_inspections",
        null=True,
        blank=True,
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        default=1,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    findings = models.TextField(
        max_length=2000,
        blank=True,
    )

    recommendation = models.CharField(
        max_length=30,
        choices=Recommendation.choices,
        blank=True,
    )

    requested_at = models.DateTimeField(
        auto_now_add=True,
    )

    inspected_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-requested_at"]

    def clean(self):
        super().clean()

        errors = {}

        if self.quantity is not None:
            if self.quantity < 1:
                errors["quantity"] = (
                    "Inspection quantity must be at least 1."
                )

            if self.asset_id:
                if self.quantity > self.asset.quantity:
                    errors["quantity"] = (
                        "Inspection quantity cannot exceed "
                        "the asset's total quantity."
                    )

                if (
                    self.asset.tracking_mode
                    == Asset.TrackingMode.INDIVIDUAL
                    and self.quantity != 1
                ):
                    errors["quantity"] = (
                        "Individual assets must have "
                        "inspection quantity 1."
                    )

        if self.status == self.Status.COMPLETED:
            if not self.inspected_by_id:
                errors["inspected_by"] = (
                    "A completed inspection needs an inspector."
                )

            if not self.findings or not self.findings.strip():
                errors["findings"] = (
                    "Inspection findings are required."
                )

            if not self.recommendation:
                errors["recommendation"] = (
                    "An inspection recommendation is required."
                )

            if not self.inspected_at:
                errors["inspected_at"] = (
                    "Inspection completion time is required."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"Inspection #{self.pk} - "
            f"{self.asset.name} ({self.status})"
        )


# ==========================================================
# ASSET DISPOSITION
# ==========================================================

class AssetDisposition(models.Model):

    class DispositionType(models.TextChoices):
        RETIRED = "Retired", "Retired"
        DONATED = "Donated", "Donated"
        RECYCLED = "Recycled", "Recycled"
        DISPOSED = "Disposed", "Disposed"

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        COMPLETED = "Completed", "Completed"
        CANCELLED = "Cancelled", "Cancelled"

    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="disposition_records",
    )

    inspection = models.ForeignKey(
        AssetInspection,
        on_delete=models.PROTECT,
        related_name="dispositions",
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_dispositions",
    )

    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="completed_dispositions",
        null=True,
        blank=True,
    )

    disposition_type = models.CharField(
        max_length=20,
        choices=DispositionType.choices,
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    reason = models.TextField(
        max_length=2000,
    )

    completion_notes = models.TextField(
        max_length=2000,
        blank=True,
    )

    requested_at = models.DateTimeField(
        auto_now_add=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-requested_at"]

    def clean(self):
        super().clean()

        errors = {}

        if not self.reason or not self.reason.strip():
            errors["reason"] = (
                "Disposition reason is required."
            )

        if self.asset_id and self.inspection_id:
            if self.inspection.asset_id != self.asset_id:
                errors["inspection"] = (
                    "The inspection must belong to "
                    "the same asset."
                )

            if self.inspection.status != (
                AssetInspection.Status.COMPLETED
            ):
                errors["inspection"] = (
                    "Disposition requires a completed inspection."
                )

        if self.asset_id and self.quantity is not None:
            if self.quantity > self.asset.quantity:
                errors["quantity"] = (
                    "Disposition quantity cannot exceed "
                    "the asset's total quantity."
                )

            if (
                self.asset.tracking_mode
                == Asset.TrackingMode.INDIVIDUAL
                and self.quantity != 1
            ):
                errors["quantity"] = (
                    "Individual assets require disposition quantity 1."
                )

        if self.status == self.Status.COMPLETED:
            if not self.completed_by_id:
                errors["completed_by"] = (
                    "A completed disposition needs an operator."
                )

            if not self.completed_at:
                errors["completed_at"] = (
                    "Disposition completion time is required."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"Disposition #{self.pk} - "
            f"{self.asset.name} "
            f"({self.disposition_type})"
        )

# ==========================================================
# STOCK MOVEMENT HISTORY
# ==========================================================

class StockMovement(models.Model):

    class Bucket(models.TextChoices):
        FREE = "Free", "Free"
        HELD = "Held", "Held"
        IN_TRANSIT = "InTransit", "In Transit"
        IN_USE = "InUse", "In Use"
        BLOCKED = "Blocked", "Blocked"
        RETIRED = "Retired", "Retired"

    class MovementType(models.TextChoices):
        REGISTRATION = "Registration", "Registration"
        RESERVATION = "Reservation", "Reservation"
        RESERVATION_CANCEL = (
            "ReservationCancel",
            "Reservation Cancellation",
        )
        DISPATCH = "Dispatch", "Dispatch"
        RECEIPT = "Receipt", "Receipt"
        TRANSFER_CANCEL = (
            "TransferCancel",
            "Transfer Cancellation",
        )
        MAINTENANCE_REPORT = (
            "MaintenanceReport",
            "Maintenance Report",
        )
        REPAIR_COMPLETE = (
            "RepairComplete",
            "Repair Completion",
        )
        MAINTENANCE_CANCEL = (
            "MaintenanceCancel",
            "Maintenance Cancellation",
        )
        DISPOSITION = "Disposition", "Disposition"

    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )

    movement_type = models.CharField(
        max_length=30,
        choices=MovementType.choices,
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    # Blank source represents newly registered stock.
    source = models.CharField(
        max_length=20,
        choices=Bucket.choices,
        blank=True,
    )

    destination = models.CharField(
        max_length=20,
        choices=Bucket.choices,
    )

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stock_movements",
        null=True,
        blank=True,
    )

    # Example: Reservation, Transfer, Maintenance, Disposition
    reference_type = models.CharField(
        max_length=30,
        blank=True,
    )

    # Stored as text to support different workflow key types.
    reference_id = models.CharField(
        max_length=100,
        blank=True,
    )

    notes = models.TextField(
        max_length=1000,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at", "-pk"]

        indexes = [
            models.Index(
                fields=["asset", "created_at"],
                name="stock_move_asset_time_idx",
            ),
        ]

    def clean(self):
        super().clean()

        errors = {}

        if self.quantity is not None and self.quantity < 1:
            errors["quantity"] = (
                "Movement quantity must be at least 1."
            )

        if self.source and self.source == self.destination:
            errors["destination"] = (
                "Source and destination must be different."
            )

        if (
            self.movement_type == self.MovementType.REGISTRATION
            and self.source
        ):
            errors["source"] = (
                "Registration must not have a source bucket."
            )

        if (
            self.movement_type != self.MovementType.REGISTRATION
            and not self.source
        ):
            errors["source"] = (
                "A source bucket is required."
            )

        if bool(self.reference_type) != bool(self.reference_id):
            errors["reference_id"] = (
                "Reference type and ID must be provided together."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        source = self.source or "New"

        return (
            f"{self.asset.name}: "
            f"{source} -> {self.destination} "
            f"({self.quantity})"
        )
