
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from .permissions import role_required
from workflows.models import Notification


@role_required("Custodian")
def custodian_test(request):
    return HttpResponse(
        "Access granted: Custodian role verified."
    )


@login_required
def dashboard(request):
    roles = set(
        request.user.groups.values_list("name", flat=True)
    )

    if request.user.is_superuser:
        roles.add("System Administrator")

    unread_notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()

    context = {
        "role_text": (
            ", ".join(sorted(roles))
            if roles
            else "No role assigned"
        ),
        "is_requester": "Requester" in roles,
        "is_custodian": "Custodian" in roles,
        "is_approver": "Approver/Admin" in roles,
        "unread_notifications": unread_notifications,
    }

    return render(
        request,
        "accounts/dashboard.html",
        context,
    )


@role_required("Approver/Admin")
def approver_test(request):
    return HttpResponse(
        "Access granted: Approver role verified."
    )
