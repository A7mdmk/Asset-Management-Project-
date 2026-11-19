
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from assets.models import Asset


class ResourceRequest(models.Model):

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        APPROVED = "Approved", "Approved"
        REJECTED = "Rejected", "Rejected"
        CANCELLED = "Cancelled", "Cancelled"
        EXPIRED = "Expired", "Expired"

    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="resource_requests"
    )

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="resource_requests"
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    reason = models.TextField(max_length=2000)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()

        errors = {}

        if self.quantity is not None and self.quantity < 1:
            errors["quantity"] = "Quantity must be at least 1."

        if (
            self.asset_id
            and self.quantity is not None
            and self.quantity > self.asset.quantity
        ):
            errors["quantity"] = (
                "Requested quantity exceeds the asset's total quantity."
            )

        if (
            self.requester_id
            and not self.requester.is_active
        ):
            errors["requester"] = "Requester must be active."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"Request #{self.pk}: "
            f"{self.asset.name} ({self.status})"
        )

class RequestApproval(models.Model):

    class Decision(models.TextChoices):
        APPROVED = "Approved", "Approved"
        REJECTED = "Rejected", "Rejected"

    request = models.ForeignKey(
        ResourceRequest,
        on_delete=models.PROTECT,
        related_name="approvals"
    )

    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="request_approvals"
    )

    decision = models.CharField(
        max_length=20,
        choices=Decision.choices
    )

    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()

        errors = {}

        if (
            self.request_id
            and self.approver_id
            and self.request.requester_id == self.approver_id
        ):
            errors["approver"] = (
                "Users cannot approve their own requests."
            )

        if self.approver_id and not self.approver.is_active:
            errors["approver"] = "Approver must be active."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"Request #{self.request_id}: "
            f"{self.decision} by {self.approver}"
        )
