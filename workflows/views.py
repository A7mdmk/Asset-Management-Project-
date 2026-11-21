from django.utils import timezone
from accounts.models import DepartmentApprover
from .models import RequestApproval
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.http import Http404
from .services import arrange_transfer
from .forms import ApprovalDecisionForm
from .services import dispatch_transfer
from .services import decide_request
from assets.asset_search import search_assets
from .forms import ResourceRequestForm
from .services import submit_request
from accounts.permissions import role_required
from .models import ResourceRequest
from .ai_recommendations import recommend_assets
from .models import Reservation, Transfer
from .services import confirm_transfer_receipt
from .services import report_transfer_dispute
from .services import cancel_arranged_transfer


@login_required
def ai_recommendations_view(request):
    context = {
        "user_need": "",
        "recommendations": [],
        "message": "",
        "error": "",
    }

    if request.method == "POST":
        user_need = request.POST.get("user_need", "").strip()
        context["user_need"] = user_need

        if not user_need:
            context["error"] = "Please describe the resource you need."
        elif len(user_need) > 500:
            context["error"] = "Your request must be 500 characters or fewer."
        else:
            try:
                result = recommend_assets(user_need)
                context["recommendations"] = result["recommendations"]
                context["message"] = result["message"]
            except Exception:
                context["error"] = (
                    "AI recommendations are temporarily unavailable. "
                    "Please try again later."
                )

    return render(
        request,
        "workflows/recommendations.html",
        context,
    )

@role_required("Requester")
def my_requests_view(request):
    """
    Display the authenticated requester's own
    resource requests.

    Users cannot view another requester's records.
    """

    requests = (
        ResourceRequest.objects
        .filter(requester=request.user)
        .select_related(
            "asset",
            "destination_department",
        )
        .order_by("-created_at", "-pk")
    )

    # Allow filtering by request status.
    selected_status = request.GET.get(
        "status", ""
    ).strip()

    valid_statuses = {
        value for value, label
        in ResourceRequest.Status.choices
    }

    if selected_status in valid_statuses:
        requests = requests.filter(
            status=selected_status
        )
    else:
        selected_status = ""

    paginator = Paginator(requests, 10)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "requests": page_obj.object_list,
        "selected_status": selected_status,
        "status_choices": ResourceRequest.Status.choices,
        "total_requests": paginator.count,
    }

    return render(
        request,
        "workflows/my_requests.html",
        context,
    )

@role_required("Requester")
def submit_request_view(request, asset_id):
    """
    Allow Requesters to submit resource requests
    using the existing workflow service.
    """

    # Only published, active, safe and available assets
    # can be selected from the request form.
    asset = get_object_or_404(
        search_assets(available_only=True),
        pk=asset_id,
    )

    if request.method == "POST":
        form = ResourceRequestForm(request.POST)

        if form.is_valid():
            try:
                submit_request(
                    requester=request.user,
                    asset_id=asset.pk,
                    destination_department_id=(
                        form.cleaned_data[
                            "destination_department"
                        ].pk
                    ),
                    quantity=form.cleaned_data["quantity"],
                    reason=form.cleaned_data["reason"],
                )

            except ValidationError as error:
                for message in error.messages:
                    form.add_error(None, message)

            else:
                return redirect("my_requests")

    else:
        form = ResourceRequestForm()

    return render(
        request,
        "workflows/submit_request.html",
        {
            "form": form,
            "asset": asset,
        },
    )

@role_required("Approver/Admin", "Custodian")
def approvals_view(request):
    """
    Show requests awaiting the current user's approval.

    Destination approvers see requests for their
    authorized departments.

    Source custodians see requests after destination
    acceptance has been approved.
    """

    user = request.user

    destination_requests = ResourceRequest.objects.none()
    source_requests = ResourceRequest.objects.none()

    # Only active, pending, unexpired requests
    # should appear in the approval queues.
    pending_requests = (
        ResourceRequest.objects
        .filter(
            status=ResourceRequest.Status.PENDING,
            expires_at__gt=timezone.now(),
            destination_department__is_active=True,
        )
        .exclude(requester=user)
    )

    # STAGE 1: DESTINATION ACCEPTANCE

    if user.groups.filter(name="Approver/Admin").exists():

        authorized_departments = (
            DepartmentApprover.objects
            .filter(
                user=user,
                is_active=True,
                department__is_active=True,
            )
            .values_list("department_id", flat=True)
        )

        destination_requests = (
            pending_requests
            .filter(
                destination_department_id__in=(
                    authorized_departments
                ),
            )
            .exclude(approvals__isnull=False)
            .select_related(
                "asset",
                "requester",
                "destination_department",
            )
            .order_by("created_at", "pk")
        )

    # STAGE 2: SOURCE CUSTODIAN RELEASE

    if user.groups.filter(name="Custodian").exists():

        source_requests = (
            pending_requests
            .filter(
                asset__custodian=user,
                approvals__stage=(
                    RequestApproval.Stage.DESTINATION
                ),
                approvals__decision=(
                    RequestApproval.Decision.APPROVED
                ),
            )
            .exclude(
                approvals__stage=RequestApproval.Stage.SOURCE
            )
            .exclude(
                approvals__approver=user
            )
            .select_related(
                "asset",
                "requester",
                "destination_department",
            )
            .distinct()
            .order_by("created_at", "pk")
        )

    return render(
        request,
        "workflows/approvals.html",
        {
            "destination_requests": destination_requests,
            "source_requests": source_requests,
        },
    )

@role_required("Approver/Admin", "Custodian")
def approval_decision_view(request, request_id, stage):
    """
    Review and decide an eligible resource request.

    Stage and authorization are validated on the
    server. The submitted form cannot choose a stage.
    """

    valid_stages = {
        RequestApproval.Stage.DESTINATION,
        RequestApproval.Stage.SOURCE,
    }

    if stage not in valid_stages:
        raise Http404("Invalid approval stage.")

    resource_request = get_object_or_404(
        ResourceRequest.objects.select_related(
            "asset",
            "requester",
            "destination_department",
        ),
        pk=request_id,
    )

    user = request.user

    # Decisions are only possible on active,
    # pending and unexpired requests.
    if (
        resource_request.status
        != ResourceRequest.Status.PENDING
        or resource_request.expires_at <= timezone.now()
        or resource_request.requester_id == user.pk
    ):
        raise PermissionDenied

    previous_approvals = list(
        resource_request.approvals.all()
    )

    # No stage may be decided more than once.
    if any(
        approval.stage == stage
        for approval in previous_approvals
    ):
        raise PermissionDenied

    if stage == RequestApproval.Stage.DESTINATION:

        # Stage 1 must be the first decision.
        if previous_approvals:
            raise PermissionDenied

        authorized = (
            user.groups.filter(
                name="Approver/Admin"
            ).exists()
            and DepartmentApprover.objects.filter(
                user=user,
                department_id=(
                    resource_request.destination_department_id
                ),
                department__is_active=True,
                is_active=True,
            ).exists()
        )

    else:
        # Stage 2 requires successful destination
        # approval by a different person.
        destination_approval = next(
            (
                approval
                for approval in previous_approvals
                if (
                    approval.stage
                    == RequestApproval.Stage.DESTINATION
                    and approval.decision
                    == RequestApproval.Decision.APPROVED
                )
            ),
            None,
        )

        authorized = (
            user.groups.filter(
                name="Custodian"
            ).exists()
            and resource_request.asset.custodian_id
            == user.pk
            and resource_request.destination_department_id
            is not None
            and resource_request.destination_department.is_active
            and destination_approval is not None
            and destination_approval.approver_id
            != user.pk
        )

    if not authorized:
        raise PermissionDenied

    if request.method == "POST":
        form = ApprovalDecisionForm(request.POST)

        if form.is_valid():
            try:
                decide_request(
                    approver=user,
                    request_id=resource_request.pk,
                    stage=stage,
                    decision=form.cleaned_data["decision"],
                    comment=form.cleaned_data["comment"],
                )

            except ValidationError as error:
                for message in error.messages:
                    form.add_error(None, message)

            else:
                return redirect("approvals")

    else:
        form = ApprovalDecisionForm()

    return render(
        request,
        "workflows/approval_decision.html",
        {
            "form": form,
            "resource_request": resource_request,
            "stage": stage,
            "is_destination_stage": (
                stage == RequestApproval.Stage.DESTINATION
            ),
        },
    )

@role_required("Custodian")
def transfer_management_view(request):
    """
    Display approved reservations and transfers
    for assets assigned to this source custodian.
    """

    reservations = (
        Reservation.objects
        .filter(
            request__asset__custodian=request.user,
            status=Reservation.Status.APPROVED,
        )
        .select_related(
            "request",
            "request__asset",
            "request__requester",
            "request__destination_department",
        )
        .order_by("-approved_at", "-pk")
    )

    transfers = (
        Transfer.objects
        .filter(
            reservation__request__asset__custodian=request.user,
        )
        .select_related(
            "reservation",
            "reservation__request",
            "reservation__request__asset",
            "reservation__request__requester",
            "reservation__request__destination_department",
        )
        .order_by("-arranged_at", "-pk")
    )

    selected_status = request.GET.get(
        "status", ""
    ).strip()

    valid_statuses = {
        value
        for value, label in Transfer.Status.choices
    }

    if selected_status in valid_statuses:
        transfers = transfers.filter(
            status=selected_status
        )
    else:
        selected_status = ""

    reservation_count = reservations.count()
    transfer_count = transfers.count()

    reservation_page = Paginator(
        reservations, 10
    ).get_page(
        request.GET.get("reservation_page")
    )

    transfer_page = Paginator(
        transfers, 10
    ).get_page(
        request.GET.get("transfer_page")
    )

    return render(
        request,
        "workflows/transfers.html",
        {
            "reservations": reservation_page.object_list,
            "transfers": transfer_page.object_list,
            "reservation_page": reservation_page,
            "transfer_page": transfer_page,
            "reservation_count": reservation_count,
            "transfer_count": transfer_count,
            "selected_status": selected_status,
            "status_choices": Transfer.Status.choices,
        },
    )

@role_required("Custodian")
def arrange_transfer_view(request, reservation_id):
    """
    Arrange an approved reservation for an asset
    assigned to the current source custodian.
    """

    reservation = get_object_or_404(
        Reservation.objects.select_related(
            "request",
            "request__asset",
        ),
        pk=reservation_id,
    )

    # The custodian must own the source asset.
    if reservation.request.asset.custodian_id != request.user.pk:
        raise PermissionDenied

    # Never change transfer state through GET.
    if request.method != "POST":
        return redirect("transfer_management")

    try:
        arrange_transfer(
            actor=request.user,
            reservation_id=reservation.pk,
        )

    except ValidationError as error:
        errors = (
            error.messages
            if hasattr(error, "messages")
            else [str(error)]
        )

        return render(
            request,
            "workflows/transfer_action_error.html",
            {
                "errors": errors,
                "reservation": reservation,
            },
            status=400,
        )

    return redirect("transfer_management")

@role_required("Custodian")
def dispatch_transfer_view(request, transfer_id):
    """
    Dispatch an arranged transfer.

    Only the assigned source custodian can dispatch
    the transfer. The existing service handles stock
    movements, status changes, and validation.
    """

    transfer = get_object_or_404(
        Transfer.objects.select_related(
            "reservation",
            "reservation__request",
            "reservation__request__asset",
        ),
        pk=transfer_id,
    )

    asset = transfer.reservation.request.asset

    if asset.custodian_id != request.user.pk:
        raise PermissionDenied

    # State-changing actions require POST.
    if request.method != "POST":
        return redirect("transfer_management")

    try:
        dispatch_transfer(
            actor=request.user,
            transfer_id=transfer.pk,
        )

    except ValidationError as error:
        errors = (
            error.messages
            if hasattr(error, "messages")
            else [str(error)]
        )

        return render(
            request,
            "workflows/transfer_action_error.html",
            {
                "errors": errors,
                "transfer": transfer,
            },
            status=400,
        )

    return redirect("transfer_management")

@role_required("Approver/Admin")
def incoming_transfers_view(request):
    """
    Display incoming transfers for departments where
    the current user is an active destination approver.
    """

    authorized_department_ids = (
        DepartmentApprover.objects.filter(
            user=request.user,
            is_active=True,
            department__is_active=True,
        )
        .values_list("department_id", flat=True)
    )

    transfers = (
        Transfer.objects
        .filter(
            reservation__request__destination_department_id__in=(
                authorized_department_ids
            ),
        )
        .select_related(
            "reservation",
            "reservation__request",
            "reservation__request__asset",
            "reservation__request__requester",
            "reservation__request__destination_department",
        )
        .order_by("-arranged_at", "-pk")
    )

    selected_status = request.GET.get(
        "status", ""
    ).strip()

    valid_statuses = {
        value for value, label in Transfer.Status.choices
    }

    if selected_status in valid_statuses:
        transfers = transfers.filter(
            status=selected_status
        )
    else:
        selected_status = ""

    paginator = Paginator(transfers, 10)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    return render(
        request,
        "workflows/incoming_transfers.html",
        {
            "transfers": page_obj.object_list,
            "page_obj": page_obj,
            "total_transfers": paginator.count,
            "selected_status": selected_status,
            "status_choices": Transfer.Status.choices,
        },
    )

@role_required("Approver/Admin")
def confirm_transfer_receipt_view(request, transfer_id):
    if request.method != "POST":
        return redirect("incoming_transfers")

    transfer = get_object_or_404(
        Transfer.objects.select_related(
            "reservation__request__destination_department",
        ),
        pk=transfer_id,
    )

    department = transfer.reservation.request.destination_department

    is_authorized = DepartmentApprover.objects.filter(
        user=request.user,
        department=department,
        is_active=True,
        department__is_active=True,
    ).exists()

    if not is_authorized:
        raise PermissionDenied

    try:
        confirm_transfer_receipt(
            actor=request.user,
            transfer_id=transfer.pk,
        )
    except ValidationError as error:
        errors = (
            error.messages
            if hasattr(error, "messages")
            else [str(error)]
        )

        return render(
            request,
            "workflows/transfer_action_error.html",
            {
                "errors": errors,
                "transfer": transfer,
            },
            status=400,
        )

    return redirect("incoming_transfers")

@role_required("Approver/Admin")
def report_transfer_dispute_view(request, transfer_id):
    if request.method != "POST":
        return redirect("incoming_transfers")

    transfer = get_object_or_404(
        Transfer.objects.select_related(
            "reservation__request__destination_department",
        ),
        pk=transfer_id,
    )

    department = transfer.reservation.request.destination_department

    is_authorized = DepartmentApprover.objects.filter(
        user=request.user,
        department=department,
        is_active=True,
        department__is_active=True,
    ).exists()

    if not is_authorized:
        raise PermissionDenied

    reason = request.POST.get("reason", "").strip()

    try:
        if not reason:
            raise ValidationError(
                "A dispute reason is required."
            )

        if len(reason) > 2000:
            raise ValidationError(
                "Dispute reason cannot exceed 2000 characters."
            )

        report_transfer_dispute(
            actor=request.user,
            transfer_id=transfer.pk,
            reason=reason,
        )

    except ValidationError as error:
        errors = (
            error.messages
            if hasattr(error, "messages")
            else [str(error)]
        )

        return render(
            request,
            "workflows/transfer_action_error.html",
            {
                "errors": errors,
                "transfer": transfer,
            },
            status=400,
        )

    return redirect("incoming_transfers")

@role_required("Custodian")
def cancel_arranged_transfer_view(request, transfer_id):
    if request.method != "POST":
        return redirect("transfer_management")

    transfer = get_object_or_404(
        Transfer.objects.select_related(
            "reservation__request__asset",
        ),
        pk=transfer_id,
    )

    asset = transfer.reservation.request.asset

    if asset.custodian_id != request.user.pk:
        raise PermissionDenied

    reason = request.POST.get("reason", "").strip()

    try:
        if not reason:
            raise ValidationError(
                "A cancellation reason is required."
            )

        if len(reason) > 2000:
            raise ValidationError(
                "Cancellation reason cannot exceed 2000 characters."
            )

        cancel_arranged_transfer(
            actor=request.user,
            transfer_id=transfer.pk,
            reason=reason,
        )

    except ValidationError as error:
        errors = (
            error.messages
            if hasattr(error, "messages")
            else [str(error)]
        )

        return render(
            request,
            "workflows/transfer_action_error.html",
            {
                "errors": errors,
                "transfer": transfer,
            },
            status=400,
        )

    return redirect("transfer_management")
