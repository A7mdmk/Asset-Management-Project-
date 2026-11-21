
from django.db.models import Sum

from .models import (
    Asset,
    AssetMaintenance,
    AssetDisposition,
    StockBalance,
)
from workflows.models import Transfer


def get_sustainability_summary():
    """
    Return sustainability indicators based on recorded
    asset-management activity.
    """

    completed_transfers = Transfer.objects.filter(
        status=Transfer.Status.RECEIVED
    )

    reused_units = (
        completed_transfers.aggregate(
            total=Sum("quantity")
        )["total"] or 0
    )

    completed_repairs = AssetMaintenance.objects.filter(
        status=AssetMaintenance.Status.COMPLETED
    )

    repaired_units = (
        completed_repairs.aggregate(
            total=Sum("quantity")
        )["total"] or 0
    )

    donated_units = (
        AssetDisposition.objects.filter(
            status=AssetDisposition.Status.COMPLETED,
            disposition_type=AssetDisposition.DispositionType.DONATED,
        ).aggregate(total=Sum("quantity"))["total"] or 0
    )

    recycled_units = (
        AssetDisposition.objects.filter(
            status=AssetDisposition.Status.COMPLETED,
            disposition_type=AssetDisposition.DispositionType.RECYCLED,
        ).aggregate(total=Sum("quantity"))["total"] or 0
    )

    available_units = (
        StockBalance.objects.aggregate(
            total=Sum("free")
        )["total"] or 0
    )

    total_registered_assets = Asset.objects.count()

    return {
        "total_registered_assets": total_registered_assets,
        "available_units": available_units,
        "reused_units": reused_units,
        "repaired_units": repaired_units,
        "donated_units": donated_units,
        "recycled_units": recycled_units,
    }

def get_sustainability_data_readiness():
    """
    Check whether asset records contain information
    useful for future sustainability estimates.

    No financial or carbon savings are calculated.
    """

    assets = Asset.objects.all()

    total_assets = assets.count()

    assets_with_value = assets.filter(
        estimated_value_aed__isnull=False,
    ).count()

    assets_with_mass = assets.filter(
        mass_kg__isnull=False,
    ).count()

    assets_with_both = assets.filter(
        estimated_value_aed__isnull=False,
        mass_kg__isnull=False,
    ).count()

    return {
        "total_assets": total_assets,
        "assets_with_value": assets_with_value,
        "assets_with_mass": assets_with_mass,
        "assets_with_both": assets_with_both,
        "assets_missing_value": (
            total_assets - assets_with_value
        ),
        "assets_missing_mass": (
            total_assets - assets_with_mass
        ),
    }
