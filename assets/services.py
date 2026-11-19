
from django.db import transaction

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
