
from django.db.models import Sum

from assets.models import (
    Asset,
    AssetMaintenance,
    AssetDisposition,
)
from workflows.models import ResourceRequest, Transfer

from assets.sustainability_services import (
    get_sustainability_summary,
)


def get_operational_report():
    """
    Generate operational statistics from recorded
    resource requests and asset-management activities.
    """

    requests = ResourceRequest.objects.all()
    transfers = Transfer.objects.all()

    completed_transfers = transfers.filter(
        status=Transfer.Status.RECEIVED
    )

    maintenance = AssetMaintenance.objects.all()

    completed_dispositions = AssetDisposition.objects.filter(
        status=AssetDisposition.Status.COMPLETED
    )

    sustainability = get_sustainability_summary()

    return {
        "total_assets": Asset.objects.count(),

        "total_requests": requests.count(),

        "pending_requests": requests.filter(
            status=ResourceRequest.Status.PENDING
        ).count(),

        "approved_requests": requests.filter(
            status=ResourceRequest.Status.APPROVED
        ).count(),

        "rejected_requests": requests.filter(
            status=ResourceRequest.Status.REJECTED
        ).count(),

        "expired_requests": requests.filter(
            status=ResourceRequest.Status.EXPIRED
        ).count(),

        "cancelled_requests": requests.filter(
            status=ResourceRequest.Status.CANCELLED
        ).count(),

        "total_transfers": transfers.count(),

        "completed_transfers": completed_transfers.count(),

        "transferred_units": (
            completed_transfers.aggregate(
                total=Sum("quantity")
            )["total"] or 0
        ),

        "total_maintenance": maintenance.count(),

        "completed_maintenance": maintenance.filter(
            status=AssetMaintenance.Status.COMPLETED
        ).count(),

        "completed_dispositions": completed_dispositions.count(),

        "sustainability": sustainability,
    }
