
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from assets.models import Asset, Department


def default_request_expiry():
    return timezone.now() + timedelta(hours=48)


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

    destination_department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="incoming_resource_requests",
        null=True,
        blank=True,
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

    expires_at = models.DateTimeField(
        default=default_request_expiry
    )

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

        if self.requester_id and not self.requester.is_active:
            errors["requester"] = "Requester must be active."

        if (
            self.destination_department_id
            and not self.destination_department.is_active
        ):
            errors["destination_department"] = (
                "Destination department must be active."
            )

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

    class Stage(models.TextChoices):
        DESTINATION = "Destination", "Destination Acceptance"
        SOURCE = "Source", "Source Release"

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

    stage = models.CharField(
        max_length=20,
        choices=Stage.choices,
        default=Stage.DESTINATION
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
            f"{self.stage} - {self.decision} by {self.approver}"
        )

class Reservation(models.Model):

    class Status(models.TextChoices):
        APPROVED = "Approved", "Approved"
        CONVERTED = "Converted", "Converted"
        CANCELLED = "Cancelled", "Cancelled"

    request = models.OneToOneField(
        ResourceRequest,
        on_delete=models.PROTECT,
        related_name="reservation",
    )

    source_approval = models.OneToOneField(
        RequestApproval,
        on_delete=models.PROTECT,
        related_name="reservation",
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.APPROVED,
    )

    approved_at = models.DateTimeField(
        default=timezone.now
    )

    cancellation_reason = models.TextField(
        blank=True
    )

    def clean(self):
        super().clean()

        errors = {}

        if self.request_id and self.quantity != self.request.quantity:
            errors["quantity"] = (
                "Reservation quantity must match the request."
            )

        if self.source_approval_id:
            if (
                self.source_approval.stage
                != RequestApproval.Stage.SOURCE
                or self.source_approval.decision
                != RequestApproval.Decision.APPROVED
            ):
                errors["source_approval"] = (
                    "A successful source approval is required."
                )

            elif (
                self.request_id
                and self.source_approval.request_id != self.request_id
            ):
                errors["source_approval"] = (
                    "Source approval must belong to this request."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"Reservation #{self.pk} - "
            f"Request #{self.request_id} ({self.status})"
        )

class Transfer(models.Model):

    class Status(models.TextChoices):
        ARRANGED = "Arranged", "Arranged"
        DISPATCHED = "Dispatched", "Dispatched"
        RECEIVED = "Received", "Received"
        DISPUTED = "Disputed", "Disputed"
        CANCELLED = "Cancelled", "Cancelled"

    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.PROTECT,
        related_name="transfer",
    )

    arranged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="arranged_transfers",
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ARRANGED,
    )

    arranged_at = models.DateTimeField(
        default=timezone.now
    )

    dispatched_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    received_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="received_transfers",
        null=True,
        blank=True,
    )


    dispute_reason = models.TextField(blank=True)

    disputed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="disputed_transfers",
        null=True,
        blank=True,
    )

    disputed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    cancellation_reason = models.TextField(blank=True)

    def clean(self):
        super().clean()

        errors = {}

        if self.reservation_id:
            if self.quantity != self.reservation.quantity:
                errors["quantity"] = (
                    "Transfer quantity must match "
                    "the reservation quantity."
                )

        if self.arranged_by_id and not self.arranged_by.is_active:
            errors["arranged_by"] = (
                "The arranging user must be active."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"Transfer #{self.pk} - "
            f"Reservation #{self.reservation_id} "
            f"({self.status})"
        )
