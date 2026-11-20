from django.db.models import Sum
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import (
    Asset,
    StockBalance,
    AssetSpecification,
    AssetAttachment,
    AssetMaintenance,
    AssetInspection,
    AssetDisposition,
)
from django.utils import timezone
from pathlib import Path
from django.core.exceptions import ValidationError
def initialize_stock(asset):
    available = asset.condition in (
        Asset.Condition.GOOD,
        Asset.Condition.FAIR,
    )

    stock = StockBalance(
        asset=asset,
        free=asset.quantity if available else 0,
        blocked=0 if available else asset.quantity,
    )

    stock.full_clean()
    stock.save()
    return stock


@transaction.atomic
def register_asset(**asset_data):
    asset = Asset(**asset_data)
    asset.full_clean()
    asset.save()

    initialize_stock(asset)

    return asset

@transaction.atomic
def change_asset_publication(*, actor, asset_id, publication):
    if not actor.is_authenticated or not actor.is_active:
        raise ValidationError(
            "An active account is required."
        )

    if publication not in (
        Asset.Publication.PUBLISHED,
        Asset.Publication.WITHDRAWN,
    ):
        raise ValidationError(
            "Invalid publication action."
        )

    asset = Asset.objects.select_for_update().get(
        pk=asset_id
    )

    # Only the assigned custodian or a superuser
    # can manage the asset's publication status.
    authorized = (
        actor.is_superuser
        or (
            asset.custodian_id == actor.pk
            and actor.groups.filter(
                name="Custodian"
            ).exists()
        )
    )

    if not authorized:
        raise ValidationError(
            "Only the assigned custodian or a superuser "
            "can manage publication."
        )

    if asset.publication == publication:
        raise ValidationError(
            "The asset already has this publication status."
        )

    if publication == Asset.Publication.PUBLISHED:
        if asset.lifecycle != Asset.Lifecycle.ACTIVE:
            raise ValidationError(
                "Only active assets can be published."
            )

        if asset.condition not in (
            Asset.Condition.GOOD,
            Asset.Condition.FAIR,
        ):
            raise ValidationError(
                "Only safe assets can be published."
            )

        if not asset.department.is_active:
            raise ValidationError(
                "The asset's department is inactive."
            )

        # Confirm the asset has a stock record.
        stock = StockBalance.objects.select_for_update().get(
            asset=asset
        )

        stock.full_clean()

    # Publication changes never move stock.
    asset.publication = publication

    asset.full_clean()
    asset.save(
        update_fields=[
            "publication",
            "updated_at",
        ]
    )

    return asset

def validate_asset_metadata_permission(*, actor, asset):
    """
    Check whether a user can manage an asset's
    specifications and attachments.

    Authorized:
    - Active superusers
    - Active assigned custodians in the Custodian group
    """

    from django.core.exceptions import ValidationError

    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
    ):
        raise ValidationError(
            "An active account is required."
        )

    if actor.is_superuser:
        return

    is_assigned_custodian = (
        asset.custodian_id == actor.pk
        and actor.groups.filter(
            name="Custodian"
        ).exists()
    )

    if not is_assigned_custodian:
        raise ValidationError(
            "Only the assigned custodian or a superuser "
            "can manage asset metadata."
        )

# ==========================================================
# ASSET SPECIFICATION MANAGEMENT
# ==========================================================

@transaction.atomic
def add_asset_specification(*, actor, asset_id, name, value):
    """
    Add a specification to an existing asset.
    """

    asset = Asset.objects.select_for_update().get(
        pk=asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    specification = AssetSpecification(
        asset=asset,
        name=name,
        value=value,
    )

    specification.full_clean()
    specification.save()

    return specification


@transaction.atomic
def update_asset_specification(
    *,
    actor,
    specification_id,
    name=None,
    value=None,
):
    """
    Update an existing asset specification.
    """

    specification = (
        AssetSpecification.objects
        .select_related("asset")
        .get(pk=specification_id)
    )

    # Lock the parent asset to coordinate metadata changes.
    asset = Asset.objects.select_for_update().get(
        pk=specification.asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    if name is not None:
        specification.name = name

    if value is not None:
        specification.value = value

    specification.full_clean()
    specification.save()

    return specification


@transaction.atomic
def delete_asset_specification(*, actor, specification_id):
    """
    Delete a specification without changing asset stock.
    """

    specification = (
        AssetSpecification.objects
        .select_related("asset")
        .get(pk=specification_id)
    )

    asset = Asset.objects.select_for_update().get(
        pk=specification.asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    specification.delete()

# ==========================================================
# ASSET ATTACHMENT UPLOAD MANAGEMENT
# ==========================================================

def validate_asset_attachment_file(uploaded_file):
    """
    Validate attachment size, extension, and file signature.

    Supported formats:
    - PDF
    - JPG / JPEG
    - PNG
    """

    if uploaded_file is None:
        raise ValidationError("An attachment file is required.")

    allowed_extensions = {".pdf", ".jpg", ".jpeg", ".png"}

    extension = Path(uploaded_file.name).suffix.lower()

    if extension not in allowed_extensions:
        raise ValidationError(
            "Only PDF, JPG, JPEG, and PNG files are allowed."
        )

    max_size = 10 * 1024 * 1024

    if uploaded_file.size > max_size:
        raise ValidationError(
            "Attachment size cannot exceed 10 MB."
        )

    if uploaded_file.size == 0:
        raise ValidationError(
            "Empty attachment files are not allowed."
        )

    if not hasattr(uploaded_file, "seek"):
        raise ValidationError(
            "Attachment must be a readable uploaded file."
        )

    try:
        uploaded_file.seek(0)
        signature = uploaded_file.read(16)
        uploaded_file.seek(0)
    except (OSError, ValueError, AttributeError) as exc:
        raise ValidationError(
            "Unable to read the attachment."
        ) from exc

    if extension == ".pdf":
        valid_signature = signature.startswith(b"%PDF-")

    elif extension in {".jpg", ".jpeg"}:
        valid_signature = signature.startswith(
            b"\xff\xd8\xff"
        )

    elif extension == ".png":
        valid_signature = signature.startswith(
            b"\x89PNG\r\n\x1a\n"
        )

    else:
        valid_signature = False

    if not valid_signature:
        raise ValidationError(
            "Attachment content does not match its file extension."
        )



@transaction.atomic
def add_asset_attachment(
    *,
    actor,
    asset_id,
    title,
    attachment_type,
    uploaded_file,
):
    """
    Upload an attachment for an existing asset.

    Only authorized users can upload.

    Clean up the stored file if the attachment
    database save raises an exception.
    """

    asset = Asset.objects.select_for_update().get(
        pk=asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    validate_asset_attachment_file(uploaded_file)

    attachment = AssetAttachment(
        asset=asset,
        title=title,
        attachment_type=attachment_type,
        file=uploaded_file,
    )

    attachment.full_clean()

    try:
        attachment.save()

    except Exception:
        # A failed database save can leave the
        # uploaded physical file in storage.

        if (
            attachment.file
            and attachment.file._committed
            and attachment.file.name
        ):
            try:
                attachment.file.delete(save=False)
            except Exception:
                # Preserve the original database error.
                # A storage cleanup failure must be
                # handled separately through monitoring.
                pass

        raise

    return attachment


# ==========================================================
# ASSET ATTACHMENT UPDATE AND DELETE
# ==========================================================

@transaction.atomic
def update_asset_attachment(
    *,
    actor,
    attachment_id,
    title=None,
    attachment_type=None,
):
    """
    Update attachment metadata.

    Replacing the physical file is not supported here.
    """

    attachment = AssetAttachment.objects.get(
        pk=attachment_id
    )

    asset = Asset.objects.select_for_update().get(
        pk=attachment.asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    attachment = AssetAttachment.objects.select_for_update().get(
        pk=attachment_id,
        asset_id=asset.pk,
    )

    if title is not None:
        attachment.title = title

    if attachment_type is not None:
        attachment.attachment_type = attachment_type

    attachment.full_clean()
    attachment.save(
        update_fields=["title", "attachment_type"]
    )

    return attachment


@transaction.atomic
def delete_asset_attachment(*, actor, attachment_id):
    """
    Delete an attachment database record.

    Delete its stored file only after the database
    transaction has successfully committed.
    """

    attachment = AssetAttachment.objects.get(
        pk=attachment_id
    )

    asset = Asset.objects.select_for_update().get(
        pk=attachment.asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    attachment = AssetAttachment.objects.select_for_update().get(
        pk=attachment_id,
        asset_id=asset.pk,
    )

    storage = attachment.file.storage
    file_name = attachment.file.name

    attachment.delete()

    if file_name:
        transaction.on_commit(
            lambda storage=storage, file_name=file_name: (
                storage.delete(file_name)
            )
        )

# ==========================================================
# ASSET MAINTENANCE MANAGEMENT
# ==========================================================

@transaction.atomic
def report_asset_maintenance(
    *,
    actor,
    asset_id,
    title,
    description,
    quantity=1,
):
    """
    Report an equipment maintenance issue.

    Move affected stock from Free to Blocked.

    Existing reservations and transfers
    are not modified.
    """

    asset = Asset.objects.select_for_update().get(
        pk=asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    if asset.lifecycle != Asset.Lifecycle.ACTIVE:
        raise ValidationError(
            "Only active assets can enter maintenance."
        )

    if not isinstance(quantity, int) or isinstance(
        quantity, bool
    ):
        raise ValidationError(
            "Maintenance quantity must be a whole number."
        )

    if quantity < 1:
        raise ValidationError(
            "Maintenance quantity must be at least 1."
        )

    stock = StockBalance.objects.select_for_update().get(
        asset=asset
    )

    if stock.free < quantity:
        raise ValidationError(
            "Insufficient free stock for maintenance."
        )

    maintenance = AssetMaintenance(
        asset=asset,
        reported_by=actor,
        title=title,
        description=description,
        quantity=quantity,
        status=AssetMaintenance.Status.REPORTED,
    )

    maintenance.full_clean()

    # Reserve the affected quantity for repair.
    stock.free -= quantity
    stock.blocked += quantity

    stock.full_clean()
    stock.save(
        update_fields=[
            "free",
            "blocked",
            "updated_at",
        ]
    )

    maintenance.save()

    validate_maintenance_stock_integrity(
        asset=asset,
        stock=stock,
    )

    return maintenance



# ==========================================================
# START ASSET REPAIR
# ==========================================================

@transaction.atomic
def start_asset_repair(*, actor, maintenance_id):
    """
    Start an existing maintenance job.

    Reported -> InProgress

    Stock remains blocked.
    """

    # Find the asset before acquiring locks.
    maintenance_reference = AssetMaintenance.objects.get(
        pk=maintenance_id
    )

    # Lock the asset first, matching the lock order
    # used by maintenance reporting and stock workflows.
    asset = Asset.objects.select_for_update().get(
        pk=maintenance_reference.asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    maintenance = (
        AssetMaintenance.objects.select_for_update()
        .get(
            pk=maintenance_id,
            asset_id=asset.pk,
        )
    )

    if maintenance.status != AssetMaintenance.Status.REPORTED:
        raise ValidationError(
            "Only reported maintenance can be started."
        )

    if asset.lifecycle != Asset.Lifecycle.ACTIVE:
        raise ValidationError(
            "Only active assets can undergo repair."
        )

    stock = StockBalance.objects.select_for_update().get(
        asset=asset
    )

    # The previously blocked quantity must still exist.
    if stock.blocked < maintenance.quantity:
        raise ValidationError(
            "Insufficient blocked stock for this maintenance."
        )

    stock.full_clean()

    maintenance.status = AssetMaintenance.Status.IN_PROGRESS
    maintenance.started_at = timezone.now()

    maintenance.full_clean()
    maintenance.save(
        update_fields=[
            "status",
            "started_at",
        ]
    )
    validate_maintenance_stock_integrity(
    asset=asset,
    stock=stock,
)
    return maintenance

# ==========================================================
# COMPLETE ASSET REPAIR
# ==========================================================

@transaction.atomic
def complete_asset_repair(
    *,
    actor,
    maintenance_id,
    repair_notes,
    return_to_service,
):
    """
    Complete an existing repair.

    If return_to_service=True:
        Blocked -> Free

    If return_to_service=False:
        Stock remains Blocked.

    Existing reservations and transfers
    are not modified.
    """

    maintenance_reference = AssetMaintenance.objects.get(
        pk=maintenance_id
    )

    # Lock the asset first.
    asset = Asset.objects.select_for_update().get(
        pk=maintenance_reference.asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    maintenance = (
        AssetMaintenance.objects.select_for_update()
        .get(
            pk=maintenance_id,
            asset_id=asset.pk,
        )
    )

    if maintenance.status != AssetMaintenance.Status.IN_PROGRESS:
        raise ValidationError(
            "Only repairs in progress can be completed."
        )

    if not isinstance(repair_notes, str) or not repair_notes.strip():
        raise ValidationError(
            "Repair completion notes are required."
        )

    if not isinstance(return_to_service, bool):
        raise ValidationError(
            "Return-to-service must be True or False."
        )

    stock = StockBalance.objects.select_for_update().get(
        asset=asset
    )

    stock.full_clean()

    if stock.blocked < maintenance.quantity:
        raise ValidationError(
            "Insufficient blocked stock for this repair."
        )

    if return_to_service:
        if asset.lifecycle != Asset.Lifecycle.ACTIVE:
            raise ValidationError(
                "Only active assets can return to service."
            )

        if asset.condition not in (
            Asset.Condition.GOOD,
            Asset.Condition.FAIR,
        ):
            raise ValidationError(
                "Asset condition must be Good or Fair "
                "before returning repaired stock to service."
            )

        stock.blocked -= maintenance.quantity
        stock.free += maintenance.quantity

        stock.full_clean()
        stock.save(
            update_fields=[
                "blocked",
                "free",
                "updated_at",
            ]
        )

    # When return_to_service=False, the
    # affected units remain blocked.

    maintenance.status = AssetMaintenance.Status.COMPLETED
    maintenance.repair_notes = repair_notes.strip()
    maintenance.completed_at = timezone.now()

    maintenance.full_clean()
    maintenance.save(
        update_fields=[
            "status",
            "repair_notes",
            "completed_at",
        ]
    )
    validate_maintenance_stock_integrity(
    asset=asset,
    stock=stock,
    )

    return maintenance

# ==========================================================
# CANCEL ASSET MAINTENANCE
# ==========================================================

@transaction.atomic
def cancel_asset_maintenance(
    *,
    actor,
    maintenance_id,
    reason,
):
    """
    Cancel a reported maintenance record.

    Only Reported -> Cancelled is allowed.

    Release the maintenance quantity:
        Blocked -> Free

    Cancellation is rejected if the asset
    cannot safely return to available stock.
    """

    maintenance_reference = AssetMaintenance.objects.get(
        pk=maintenance_id
    )

    # Lock the parent asset first to remain
    # consistent with the maintenance workflows.
    asset = Asset.objects.select_for_update().get(
        pk=maintenance_reference.asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    maintenance = (
        AssetMaintenance.objects.select_for_update()
        .get(
            pk=maintenance_id,
            asset_id=asset.pk,
        )
    )

    if maintenance.status != AssetMaintenance.Status.REPORTED:
        raise ValidationError(
            "Only reported maintenance can be cancelled."
        )

    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError(
            "A maintenance cancellation reason is required."
        )

    if asset.lifecycle != Asset.Lifecycle.ACTIVE:
        raise ValidationError(
            "Maintenance cannot be cancelled while "
            "the asset is inactive."
        )

    if asset.condition not in (
        Asset.Condition.GOOD,
        Asset.Condition.FAIR,
    ):
        raise ValidationError(
            "Maintenance cannot be cancelled while "
            "the asset condition is unsafe or requires attention."
        )

    stock = StockBalance.objects.select_for_update().get(
        asset=asset
    )

    stock.full_clean()

    if stock.blocked < maintenance.quantity:
        raise ValidationError(
            "Insufficient blocked stock for cancellation."
        )

    # Release the quantity originally reserved
    # for this maintenance record.
    stock.blocked -= maintenance.quantity
    stock.free += maintenance.quantity

    stock.full_clean()
    stock.save(
        update_fields=[
            "blocked",
            "free",
            "updated_at",
        ]
    )

    maintenance.status = AssetMaintenance.Status.CANCELLED

    # Record the cancellation reason using the
    # existing notes field to avoid another migration.
    maintenance.repair_notes = (
        f"Cancellation reason: {reason.strip()}"
    )

    maintenance.full_clean()
    maintenance.save(
        update_fields=[
            "status",
            "repair_notes",
        ]
    )
    validate_maintenance_stock_integrity(
    asset=asset,
    stock=stock,
)

    return maintenance

# ==========================================================
# MAINTENANCE STOCK INTEGRITY
# ==========================================================

def validate_maintenance_stock_integrity(
    *,
    asset,
    stock,
):
    """
    Verify that blocked stock covers all
    currently active maintenance records.

    Active maintenance statuses:
    - Reported
    - InProgress

    Does not modify stock.
    """

    active_maintenance_quantity = (
        AssetMaintenance.objects.filter(
            asset=asset,
            status__in=[
                AssetMaintenance.Status.REPORTED,
                AssetMaintenance.Status.IN_PROGRESS,
            ],
        ).aggregate(
            total=Sum("quantity")
        )["total"] or 0
    )

    if stock.blocked < active_maintenance_quantity:
        raise ValidationError(
            "Blocked stock is insufficient to cover "
            "all active maintenance records."
        )

    stock.full_clean()

    return active_maintenance_quantity

# ==========================================================
# ASSET INSPECTION MANAGEMENT
# ==========================================================

@transaction.atomic
def request_asset_inspection(
    *,
    actor,
    asset_id,
    quantity=1,
):
    """
    Create a pending asset inspection.

    Only the assigned custodian or an authorized
    superuser can request an inspection.

    Requesting an inspection does not move stock.
    """

    asset = Asset.objects.select_for_update().get(
        pk=asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    if asset.lifecycle != Asset.Lifecycle.ACTIVE:
        raise ValidationError(
            "Only active assets can be inspected."
        )

    if not isinstance(quantity, int) or isinstance(
        quantity, bool
    ):
        raise ValidationError(
            "Inspection quantity must be a whole number."
        )

    if quantity < 1:
        raise ValidationError(
            "Inspection quantity must be at least 1."
        )

    if quantity > asset.quantity:
        raise ValidationError(
            "Inspection quantity exceeds asset quantity."
        )

    if (
        asset.tracking_mode == Asset.TrackingMode.INDIVIDUAL
        and quantity != 1
    ):
        raise ValidationError(
            "Individual assets require inspection quantity 1."
        )

    stock = StockBalance.objects.select_for_update().get(
        asset=asset
    )

    stock.full_clean()

    # A request does not reserve or move stock.
    # Stock eligibility will be checked again
    # before any disposition is executed.

    inspection = AssetInspection(
        asset=asset,
        requested_by=actor,
        quantity=quantity,
        status=AssetInspection.Status.PENDING,
    )

    inspection.full_clean()
    inspection.save()

    return inspection

# ==========================================================
# COMPLETE ASSET INSPECTION
# ==========================================================

@transaction.atomic
def complete_asset_inspection(
    *,
    actor,
    inspection_id,
    findings,
    recommendation,
):
    """
    Complete a pending asset inspection.

    Records findings and a recommendation.

    Does not modify stock, condition,
    lifecycle, reservations, or transfers.
    """

    # Find the parent asset before acquiring locks.
    inspection_reference = AssetInspection.objects.get(
        pk=inspection_id
    )

    # Lock the asset first, following the
    # existing asset workflow lock order.
    asset = Asset.objects.select_for_update().get(
        pk=inspection_reference.asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    inspection = (
        AssetInspection.objects.select_for_update()
        .get(
            pk=inspection_id,
            asset_id=asset.pk,
        )
    )

    if inspection.status != AssetInspection.Status.PENDING:
        raise ValidationError(
            "Only pending inspections can be completed."
        )

    if not isinstance(findings, str) or not findings.strip():
        raise ValidationError(
            "Inspection findings are required."
        )

    valid_recommendations = {
        choice.value
        for choice in AssetInspection.Recommendation
    }

    if recommendation not in valid_recommendations:
        raise ValidationError(
            "Invalid inspection recommendation."
        )

    stock = StockBalance.objects.select_for_update().get(
        asset=asset
    )

    stock.full_clean()

    inspection.status = AssetInspection.Status.COMPLETED
    inspection.inspected_by = actor
    inspection.findings = findings.strip()
    inspection.recommendation = recommendation
    inspection.inspected_at = timezone.now()

    inspection.full_clean()
    inspection.save(
        update_fields=[
            "status",
            "inspected_by",
            "findings",
            "recommendation",
            "inspected_at",
        ]
    )

    return inspection

# ==========================================================
# CANCEL ASSET INSPECTION
# ==========================================================

@transaction.atomic
def cancel_asset_inspection(*, actor, inspection_id):
    """
    Cancel a pending asset inspection.

    Pending -> Cancelled

    Does not change stock, lifecycle,
    reservations, or transfers.
    """

    # Locate the parent asset before acquiring locks.
    inspection_reference = AssetInspection.objects.get(
        pk=inspection_id
    )

    # Lock the asset first, consistent with
    # other inspection and maintenance operations.
    asset = Asset.objects.select_for_update().get(
        pk=inspection_reference.asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    inspection = (
        AssetInspection.objects.select_for_update()
        .get(
            pk=inspection_id,
            asset_id=asset.pk,
        )
    )

    if inspection.status != AssetInspection.Status.PENDING:
        raise ValidationError(
            "Only pending inspections can be cancelled."
        )

    stock = StockBalance.objects.select_for_update().get(
        asset=asset
    )

    stock.full_clean()

    inspection.status = AssetInspection.Status.CANCELLED

    inspection.full_clean()
    inspection.save(
        update_fields=["status"]
    )

    return inspection

# ==========================================================
# REQUEST ASSET DISPOSITION
# ==========================================================

@transaction.atomic
def request_asset_disposition(
    *,
    actor,
    inspection_id,
    disposition_type,
    reason,
):
    """
    Request disposition following a completed inspection.

    Does not modify stock or asset lifecycle.
    """

    inspection_reference = AssetInspection.objects.get(
        pk=inspection_id
    )

    asset = Asset.objects.select_for_update().get(
        pk=inspection_reference.asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    inspection = (
        AssetInspection.objects.select_for_update()
        .get(
            pk=inspection_id,
            asset_id=asset.pk,
        )
    )

    if inspection.status != AssetInspection.Status.COMPLETED:
        raise ValidationError(
            "Disposition requires a completed inspection."
        )

    recommendation_mapping = {
        AssetInspection.Recommendation.RETIRE:
            AssetDisposition.DispositionType.RETIRED,

        AssetInspection.Recommendation.DONATE:
            AssetDisposition.DispositionType.DONATED,

        AssetInspection.Recommendation.RECYCLE:
            AssetDisposition.DispositionType.RECYCLED,

        AssetInspection.Recommendation.DISPOSE:
            AssetDisposition.DispositionType.DISPOSED,
    }

    expected_type = recommendation_mapping.get(
        inspection.recommendation
    )

    if (
        expected_type is None
        or disposition_type != expected_type
    ):
        raise ValidationError(
            "Disposition type must match the "
            "completed inspection recommendation."
        )

    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError(
            "A disposition reason is required."
        )

    if asset.lifecycle != Asset.Lifecycle.ACTIVE:
        raise ValidationError(
            "Only active assets can enter disposition."
        )

    # Prevent multiple dispositions for one inspection.
    if inspection.dispositions.exists():
        raise ValidationError(
            "A disposition already exists for this inspection."
        )

    stock = StockBalance.objects.select_for_update().get(
        asset=asset
    )

    stock.full_clean()

    # This request does not reserve stock.
    # Eligibility and maintenance constraints
    # are checked during disposition execution.

    disposition = AssetDisposition(
        asset=asset,
        inspection=inspection,
        requested_by=actor,
        disposition_type=disposition_type,
        quantity=inspection.quantity,
        status=AssetDisposition.Status.PENDING,
        reason=reason.strip(),
    )

    disposition.full_clean()
    disposition.save()

    return disposition

# ==========================================================
# EXECUTE ASSET DISPOSITION
# ==========================================================

@transaction.atomic
def execute_asset_disposition(
    *,
    actor,
    disposition_id,
    completion_notes,
):
    """
    Complete an approved inspection-based disposition.

    Move affected stock:
        Free -> Retired

    Held, InTransit, InUse, and Blocked stock
    must remain untouched.

    For partial lot dispositions, keep the
    overall asset lifecycle Active.
    """

    disposition_reference = AssetDisposition.objects.get(
        pk=disposition_id
    )

    # Lock the parent asset first.
    asset = Asset.objects.select_for_update().get(
        pk=disposition_reference.asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    disposition = (
        AssetDisposition.objects.select_for_update()
        .select_related("inspection")
        .get(
            pk=disposition_id,
            asset_id=asset.pk,
        )
    )

    if disposition.status != AssetDisposition.Status.PENDING:
        raise ValidationError(
            "Only pending dispositions can be executed."
        )

    if not isinstance(completion_notes, str):
        raise ValidationError(
            "Completion notes must be text."
        )

    if not completion_notes.strip():
        raise ValidationError(
            "Disposition completion notes are required."
        )

    if asset.lifecycle != Asset.Lifecycle.ACTIVE:
        raise ValidationError(
            "Only active assets can undergo disposition."
        )

    inspection = disposition.inspection

    if inspection.status != AssetInspection.Status.COMPLETED:
        raise ValidationError(
            "A completed inspection is required."
        )

    recommendation_mapping = {
        AssetInspection.Recommendation.RETIRE:
            AssetDisposition.DispositionType.RETIRED,

        AssetInspection.Recommendation.DONATE:
            AssetDisposition.DispositionType.DONATED,

        AssetInspection.Recommendation.RECYCLE:
            AssetDisposition.DispositionType.RECYCLED,

        AssetInspection.Recommendation.DISPOSE:
            AssetDisposition.DispositionType.DISPOSED,
    }

    if (
        recommendation_mapping.get(inspection.recommendation)
        != disposition.disposition_type
    ):
        raise ValidationError(
            "Disposition no longer matches "
            "the inspection recommendation."
        )

    if disposition.quantity != inspection.quantity:
        raise ValidationError(
            "Disposition quantity must match "
            "the inspected quantity."
        )

    stock = StockBalance.objects.select_for_update().get(
        asset=asset
    )

    stock.full_clean()

    # Existing maintenance and transfer stock
    # cannot be used for disposition.
    if stock.free < disposition.quantity:
        raise ValidationError(
            "Insufficient free stock for disposition."
        )

    # Preserve all existing blocked, held,
    # in-transit, and in-use balances.
    stock.free -= disposition.quantity
    stock.retired += disposition.quantity

    stock.full_clean()
    stock.save(
        update_fields=[
            "free",
            "retired",
            "updated_at",
        ]
    )

    disposition.status = AssetDisposition.Status.COMPLETED
    disposition.completed_by = actor
    disposition.completion_notes = completion_notes.strip()
    disposition.completed_at = timezone.now()

    disposition.full_clean()
    disposition.save(
        update_fields=[
            "status",
            "completed_by",
            "completion_notes",
            "completed_at",
        ]
    )

    # Only update the asset-wide lifecycle when
    # every unit is in the retired stock bucket.
    # Partial lots remain Active.
    if stock.retired == asset.quantity:
        asset.lifecycle = disposition.disposition_type
        asset.publication = Asset.Publication.WITHDRAWN

        asset.full_clean()
        asset.save(
            update_fields=[
                "lifecycle",
                "publication",
                "updated_at",
            ]
        )

    return disposition

# ==========================================================
# CANCEL ASSET DISPOSITION
# ==========================================================

@transaction.atomic
def cancel_asset_disposition(
    *,
    actor,
    disposition_id,
    reason,
):
    """
    Cancel a pending disposition.

    Pending -> Cancelled

    Does not modify stock, asset lifecycle,
    inspections, reservations, or transfers.
    """

    disposition_reference = AssetDisposition.objects.get(
        pk=disposition_id
    )

    # Lock the parent asset first.
    asset = Asset.objects.select_for_update().get(
        pk=disposition_reference.asset_id
    )

    validate_asset_metadata_permission(
        actor=actor,
        asset=asset,
    )

    disposition = (
        AssetDisposition.objects.select_for_update()
        .get(
            pk=disposition_id,
            asset_id=asset.pk,
        )
    )

    if disposition.status != AssetDisposition.Status.PENDING:
        raise ValidationError(
            "Only pending dispositions can be cancelled."
        )

    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError(
            "A disposition cancellation reason is required."
        )

    stock = StockBalance.objects.select_for_update().get(
        asset=asset
    )

    stock.full_clean()

    disposition.status = AssetDisposition.Status.CANCELLED

    # Store the cancellation reason in the
    # existing completion notes field.
    disposition.completion_notes = (
        f"Cancellation reason: {reason.strip()}"
    )

    disposition.full_clean()
    disposition.save(
        update_fields=[
            "status",
            "completion_notes",
        ]
    )

    return disposition
