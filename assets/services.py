
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Asset, StockBalance


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
