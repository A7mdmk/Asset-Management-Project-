
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.paginator import Paginator

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
