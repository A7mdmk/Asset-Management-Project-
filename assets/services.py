
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Asset, StockBalance
from .models import (
    Asset,
    StockBalance,
    AssetSpecification,
    AssetAttachment,
)
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
