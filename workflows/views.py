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

from .forms import ApprovalDecisionForm
from .services import decide_request
from assets.asset_search import search_assets
from .forms import ResourceRequestForm
from .services import submit_request
from accounts.permissions import role_required
from .models import ResourceRequest
from .ai_recommendations import recommend_assets


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
