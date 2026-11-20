
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from .asset_search import search_assets
from .models import Asset, Category, Department


@login_required
def asset_catalog(request):
    """
    Display a searchable catalog of campus assets.

    Uses the existing backend search service so that
    publication, safety, and availability rules remain
    consistent across the application.
    """

    query = request.GET.get("q", "").strip()[:200]
    category_id = request.GET.get("category", "").strip()
    department_id = request.GET.get("department", "").strip()
    condition = request.GET.get("condition", "").strip()
    available_only = request.GET.get("available", "1") != "0"

    # Accept only valid integer IDs for these filters.
    if not category_id.isdecimal():
        category_id = ""

    if not department_id.isdecimal():
        department_id = ""

    # Restrict condition filtering to safe asset conditions.
    allowed_conditions = {
        Asset.Condition.GOOD,
        Asset.Condition.FAIR,
    }

    if condition not in allowed_conditions:
        condition = ""

    assets = search_assets(
        query=query,
        category_id=int(category_id) if category_id else None,
        department_id=int(department_id) if department_id else None,
        condition=condition or None,
        available_only=available_only,
    )

    paginator = Paginator(assets, 12)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "is_requester": request.user.groups.filter(
    name="Requester"
).exists(),
        "page_obj": page_obj,
        "assets": page_obj.object_list,
        "categories": Category.objects.order_by("name"),
        "departments": Department.objects.filter(
            is_active=True
        ).order_by("name"),
        "query": query,
        "selected_category": category_id,
        "selected_department": department_id,
        "selected_condition": condition,
        "available_only": available_only,
        "total_results": paginator.count,
    }

    return render(
        request,
        "assets/catalog.html",
        context,
    )
