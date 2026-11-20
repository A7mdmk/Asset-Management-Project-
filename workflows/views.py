
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect

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
