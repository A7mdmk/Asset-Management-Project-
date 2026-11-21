from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from .models import AssetMaintenance
from .services import change_asset_publication
from .forms import AssetRegistrationForm
from .services import register_asset
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from accounts.permissions import role_required
from .asset_search import search_assets
from .models import Asset, Category, Department
from .forms import MaintenanceReportForm
from .services import report_asset_maintenance
from .services import start_asset_repair
from .forms import RepairCompletionForm
from .services import complete_asset_repair
from .forms import MaintenanceCancellationForm
from .services import cancel_asset_maintenance
from .models import AssetInspection
from .forms import InspectionRequestForm
from .services import request_asset_inspection
from .forms import InspectionCompletionForm
from .services import complete_asset_inspection
from .services import cancel_asset_inspection

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

@role_required("Custodian")
def maintenance_management_view(request):
    """
    Display maintenance records for assets assigned
    to the authenticated custodian.

    Custodians cannot view maintenance records
    belonging to other custodians.
    """

    maintenance_records = (
        AssetMaintenance.objects
        .filter(asset__custodian=request.user)
        .select_related(
            "asset",
            "asset__department",
            "reported_by",
        )
        .order_by("-reported_at", "-pk")
    )

    # Optional maintenance status filter.
    selected_status = request.GET.get(
        "status", ""
    ).strip()

    valid_statuses = {
        value
        for value, label in AssetMaintenance.Status.choices
    }

    if selected_status in valid_statuses:
        maintenance_records = maintenance_records.filter(
            status=selected_status
        )
    else:
        selected_status = ""

    paginator = Paginator(maintenance_records, 10)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "maintenance_records": page_obj.object_list,
        "page_obj": page_obj,
        "total_records": paginator.count,
        "selected_status": selected_status,
        "status_choices": AssetMaintenance.Status.choices,
    }

    return render(
        request,
        "assets/maintenance.html",
        context,
    )

@role_required("Custodian")
def maintenance_report_view(request, asset_id):
    """
    Allow an assigned custodian to report an
    asset maintenance issue.

    The existing service handles stock blocking,
    validation, and audit history.
    """

    asset = get_object_or_404(
        Asset.objects.select_related(
            "category",
            "department",
            "stock",
        ),
        pk=asset_id,
    )

    # Custodians cannot report maintenance
    # against another custodian's assets.
    if asset.custodian_id != request.user.pk:
        raise PermissionDenied

    if request.method == "POST":
        form = MaintenanceReportForm(request.POST)

        if form.is_valid():
            try:
                report_asset_maintenance(
                    actor=request.user,
                    asset_id=asset.pk,
                    title=form.cleaned_data["title"],
                    description=form.cleaned_data["description"],
                    quantity=form.cleaned_data["quantity"],
                )

            except ValidationError as error:
                if hasattr(error, "message_dict"):
                    for field, messages in error.message_dict.items():
                        target = (
                            field if field in form.fields else None
                        )
                        for message in messages:
                            form.add_error(target, message)
                else:
                    for message in error.messages:
                        form.add_error(None, message)

            else:
                return redirect("maintenance_management")

    else:
        form = MaintenanceReportForm()

    return render(
        request,
        "assets/maintenance_report.html",
        {
            "form": form,
            "asset": asset,
        },
    )

@role_required("Custodian")
def maintenance_start_view(request, maintenance_id):
    """
    Start a reported maintenance job.

    Only the assigned custodian can start repairs.
    All status and stock validation is performed
    by the existing service.
    """

    maintenance = get_object_or_404(
        AssetMaintenance.objects.select_related("asset"),
        pk=maintenance_id,
    )

    if maintenance.asset.custodian_id != request.user.pk:
        raise PermissionDenied

    # Starting a repair changes data, so require POST.
    if request.method != "POST":
        return redirect("maintenance_management")

    try:
        start_asset_repair(
            actor=request.user,
            maintenance_id=maintenance.pk,
        )
    except ValidationError as error:
        messages = (
            error.messages
            if hasattr(error, "messages")
            else [str(error)]
        )

        return render(
            request,
            "assets/maintenance_action_error.html",
            {
                "maintenance": maintenance,
                "errors": messages,
            },
            status=400,
        )

    return redirect("maintenance_management")

@role_required("Custodian")
def maintenance_complete_view(request, maintenance_id):
    """
    Complete a repair for an asset assigned to the custodian.

    The service validates the maintenance status,
    asset condition, stock integrity, and records
    any stock movement.
    """

    maintenance = get_object_or_404(
        AssetMaintenance.objects.select_related(
            "asset",
            "asset__department",
        ),
        pk=maintenance_id,
    )

    if maintenance.asset.custodian_id != request.user.pk:
        raise PermissionDenied

    if request.method == "POST":
        form = RepairCompletionForm(request.POST)

        if form.is_valid():
            try:
                complete_asset_repair(
                    actor=request.user,
                    maintenance_id=maintenance.pk,
                    repair_notes=form.cleaned_data["repair_notes"],
                    return_to_service=form.cleaned_data[
                        "return_to_service"
                    ],
                )

            except ValidationError as error:
                if hasattr(error, "message_dict"):
                    for field, error_messages in error.message_dict.items():
                        target = field if field in form.fields else None
                        for message in error_messages:
                            form.add_error(target, message)
                else:
                    for message in error.messages:
                        form.add_error(None, message)

            else:
                return redirect("maintenance_management")

    else:
        form = RepairCompletionForm()

    return render(
        request,
        "assets/maintenance_complete.html",
        {
            "form": form,
            "maintenance": maintenance,
        },
    )

@role_required("Custodian")
def maintenance_cancel_view(request, maintenance_id):
    """
    Cancel reported maintenance for an asset
    assigned to the logged-in custodian.
    """

    maintenance = get_object_or_404(
        AssetMaintenance.objects.select_related(
            "asset",
            "asset__department",
        ),
        pk=maintenance_id,
    )

    if maintenance.asset.custodian_id != request.user.pk:
        raise PermissionDenied

    if request.method == "POST":
        form = MaintenanceCancellationForm(request.POST)

        if form.is_valid():
            try:
                cancel_asset_maintenance(
                    actor=request.user,
                    maintenance_id=maintenance.pk,
                    reason=form.cleaned_data["reason"],
                )

            except ValidationError as error:
                if hasattr(error, "message_dict"):
                    for field, error_messages in error.message_dict.items():
                        target = field if field in form.fields else None
                        for message in error_messages:
                            form.add_error(target, message)
                else:
                    for message in error.messages:
                        form.add_error(None, message)

            else:
                return redirect("maintenance_management")

    else:
        form = MaintenanceCancellationForm()

    return render(
        request,
        "assets/maintenance_cancel.html",
        {
            "maintenance": maintenance,
            "form": form,
        },
    )

@role_required("Custodian")
def inspection_management_view(request):
    """
    Display inspection records for assets assigned
    to the currently logged-in custodian.
    """

    inspections = (
        AssetInspection.objects
        .filter(asset__custodian=request.user)
        .select_related(
            "asset",
            "asset__department",
            "requested_by",
            "inspected_by",
        )
        .order_by("-requested_at", "-pk")
    )

    selected_status = request.GET.get(
        "status", ""
    ).strip()

    valid_statuses = {
        value
        for value, label in AssetInspection.Status.choices
    }

    if selected_status in valid_statuses:
        inspections = inspections.filter(
            status=selected_status
        )
    else:
        selected_status = ""

    paginator = Paginator(inspections, 10)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    return render(
        request,
        "assets/inspections.html",
        {
            "inspections": page_obj.object_list,
            "page_obj": page_obj,
            "total_inspections": paginator.count,
            "selected_status": selected_status,
            "status_choices": AssetInspection.Status.choices,
        },
    )

@role_required("Custodian")
def inspection_request_view(request, asset_id):
    asset = get_object_or_404(
        Asset.objects.select_related(
            "department",
            "category",
        ),
        pk=asset_id,
    )

    if asset.custodian_id != request.user.pk:
        raise PermissionDenied

    if request.method == "POST":
        form = InspectionRequestForm(request.POST)

        if form.is_valid():
            try:
                request_asset_inspection(
                    actor=request.user,
                    asset_id=asset.pk,
                    quantity=form.cleaned_data["quantity"],
                )

            except ValidationError as error:
                messages = (
                    error.messages
                    if hasattr(error, "messages")
                    else [str(error)]
                )

                for message in messages:
                    form.add_error(None, message)

            else:
                return redirect("inspection_management")
    else:
        form = InspectionRequestForm()

    return render(
        request,
        "assets/inspection_request.html",
        {
            "asset": asset,
            "form": form,
        },
    )

@role_required("Custodian")
def inspection_complete_view(request, inspection_id):
    inspection = get_object_or_404(
        AssetInspection.objects.select_related(
            "asset",
            "asset__department",
        ),
        pk=inspection_id,
    )

    if inspection.asset.custodian_id != request.user.pk:
        raise PermissionDenied

    if inspection.status != AssetInspection.Status.PENDING:
        return redirect("inspection_management")

    if request.method == "POST":
        form = InspectionCompletionForm(request.POST)

        if form.is_valid():
            try:
                complete_asset_inspection(
                    actor=request.user,
                    inspection_id=inspection.pk,
                    findings=form.cleaned_data["findings"],
                    recommendation=form.cleaned_data["recommendation"],
                )

            except ValidationError as error:
                messages = (
                    error.messages
                    if hasattr(error, "messages")
                    else [str(error)]
                )

                for message in messages:
                    form.add_error(None, message)

            else:
                return redirect("inspection_management")

    else:
        form = InspectionCompletionForm()

    return render(
        request,
        "assets/inspection_complete.html",
        {
            "inspection": inspection,
            "form": form,
        },
    )

@role_required("Custodian")
def inspection_cancel_view(request, inspection_id):
    if request.method != "POST":
        return redirect("inspection_management")

    inspection = get_object_or_404(
        AssetInspection.objects.select_related("asset"),
        pk=inspection_id,
    )

    if inspection.asset.custodian_id != request.user.pk:
        raise PermissionDenied

    try:
        cancel_asset_inspection(
            actor=request.user,
            inspection_id=inspection.pk,
        )

    except ValidationError as error:
        messages = (
            error.messages
            if hasattr(error, "messages")
            else [str(error)]
        )

        return render(
            request,
            "assets/inspection_action_error.html",
            {
                "inspection": inspection,
                "errors": messages,
            },
            status=400,
        )

    return redirect("inspection_management")
