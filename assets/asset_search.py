
from django.db.models import Q

from .models import Asset


def search_assets(
    *,
    query="",
    category_id=None,
    department_id=None,
    condition=None,
    available_only=True,
):
    """
    Search and filter campus assets.

    Public browsing returns only published, active,
    safe assets.
    """

    assets = Asset.objects.filter(
        publication=Asset.Publication.PUBLISHED,
        lifecycle=Asset.Lifecycle.ACTIVE,
        condition__in=[
            Asset.Condition.GOOD,
            Asset.Condition.FAIR,
        ],
        category__isnull=False,
        department__is_active=True,
    ).select_related(
        "category",
        "department",
        "stock",
    )

    if available_only:
        assets = assets.filter(stock__free__gt=0)

    if query:
        assets = assets.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
            | Q(location__icontains=query)
        )

    if category_id is not None:
        assets = assets.filter(category_id=category_id)

    if department_id is not None:
        assets = assets.filter(department_id=department_id)

    if condition:
        assets = assets.filter(condition=condition)

    return assets.order_by("name", "pk")
