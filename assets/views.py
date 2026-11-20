from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .services import change_asset_publication
from .forms import AssetRegistrationForm
from .services import register_asset
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from accounts.permissions import role_required
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

@role_required("Custodian")
def asset_management_view(request):
    """
    Display assets assigned to the current custodian.

    Custodians can only see their own managed assets.
    """

    assets = (
        Asset.objects
        .filter(custodian=request.user)
        .select_related(
            "category",
            "department",
            "stock",
        )
        .order_by("name", "pk")
    )

    # Optional publication status filter.
    selected_publication = request.GET.get(
        "publication", ""
    ).strip()

    valid_publications = {
        value
        for value, label in Asset.Publication.choices
    }

    if selected_publication in valid_publications:
        assets = assets.filter(
            publication=selected_publication
        )
    else:
        selected_publication = ""

    paginator = Paginator(assets, 10)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "assets": page_obj.object_list,
        "page_obj": page_obj,
        "total_assets": paginator.count,
        "selected_publication": selected_publication,
        "publication_choices": Asset.Publication.choices,
    }

    return render(
        request,
        "assets/management.html",
        context,
    )

@role_required("Custodian")
def asset_registration_view(request):
    """
    Register a new asset for the logged-in custodian.

    Asset ownership and publication status are
    assigned on the server, not by the user.
    """

    if request.method == "POST":
        form = AssetRegistrationForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data

            try:
                register_asset(
                    name=data["name"],
                    description=data["description"],
                    asset_tag=data["asset_tag"] or None,
                    category=data["category"],
                    department=data["department"],
                    custodian=request.user,
                    location=data["location"],
                    tracking_mode=data["tracking_mode"],
                    quantity=data["quantity"],
                    condition=data["condition"],
                    lifecycle=Asset.Lifecycle.ACTIVE,
                    publication=Asset.Publication.DRAFT,
                )

            except ValidationError as error:
                if hasattr(error, "message_dict"):
                    for field, messages in error.message_dict.items():
                        target = (
                            field
                            if field in form.fields
                            else None
                        )

                        for message in messages:
                            form.add_error(target, message)
                else:
                    for message in error.messages:
                        form.add_error(None, message)

            except IntegrityError:
                form.add_error(
                    "asset_tag",
                    "This asset tag is already in use.",
                )

            else:
                return redirect("asset_management")

    else:
        form = AssetRegistrationForm()

    return render(
        request,
        "assets/register.html",
        {
            "form": form,
        },
    )

@role_required("Custodian")
def asset_publication_view(request, asset_id):
    """
    Allow custodians to publish or withdraw
    assets assigned to them.

    Publication changes require POST requests.
    """

    asset = get_object_or_404(
        Asset,
        pk=asset_id,
    )

    # A custodian cannot manage another user's assets.
    if asset.custodian_id != request.user.pk:
        raise PermissionDenied

    if request.method != "POST":
        return redirect("asset_management")

    action = request.POST.get("action", "").strip()

    allowed_actions = {
        "publish": Asset.Publication.PUBLISHED,
        "withdraw": Asset.Publication.WITHDRAWN,
    }

    publication = allowed_actions.get(action)

    if publication is None:
        raise PermissionDenied

    try:
        change_asset_publication(
            actor=request.user,
            asset_id=asset.pk,
            publication=publication,
        )

    except ValidationError as error:
        messages = (
            error.messages
            if hasattr(error, "messages")
            else [str(error)]
        )

        return render(
            request,
            "assets/publication_error.html",
            {
                "asset": asset,
                "errors": messages,
            },
            status=400,
        )

    return redirect("asset_management")
