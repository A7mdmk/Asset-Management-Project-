
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

import uuid
from django.conf import settings
from django.core.validators import MinValueValidator


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
        primary_key=True, default=uuid.uuid4, editable=False
    )
    name = models.CharField(max_length=120)
    description = models.TextField(max_length=2000, blank=True)
    asset_tag = models.CharField(
        max_length=100, unique=True, null=True, blank=True
    )

    category = models.ForeignKey(
        Category, on_delete=models.PROTECT
    )
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT
    )
    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )

    location = models.CharField(max_length=255)
    tracking_mode = models.CharField(
        max_length=20,
        choices=TrackingMode.choices,
        default=TrackingMode.INDIVIDUAL
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    condition = models.CharField(
        max_length=20,
        choices=Condition.choices,
        default=Condition.GOOD
    )
    lifecycle = models.CharField(
        max_length=20,
        choices=Lifecycle.choices,
        default=Lifecycle.ACTIVE
    )
    publication = models.CharField(
        max_length=20,
        choices=Publication.choices,
        default=Publication.DRAFT
    )

    acquisition_date = models.DateField(null=True, blank=True)
    estimated_value_aed = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)]
    )
    mass_kg = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        validators=[MinValueValidator(0)]
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        from django.utils import timezone

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


class StockBalance(models.Model):
    asset = models.OneToOneField(
        Asset,
        on_delete=models.PROTECT,
        related_name="stock"
    )

    free = models.PositiveIntegerField(default=0)
    held = models.PositiveIntegerField(default=0)
    in_transit = models.PositiveIntegerField(default=0)
    in_use = models.PositiveIntegerField(default=0)
    blocked = models.PositiveIntegerField(default=0)
    retired = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

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
        from django.core.exceptions import ValidationError

        super().clean()

        if self.asset_id and self.total != self.asset.quantity:
            raise ValidationError(
                "Stock balances must equal the asset quantity."
            )

    def __str__(self):
        return f"{self.asset.name}: {self.free} available"

