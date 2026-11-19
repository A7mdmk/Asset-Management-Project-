
from django.http import HttpResponse
from .permissions import role_required
from django.shortcuts import render

@role_required("Custodian")
def custodian_test(request):
    return HttpResponse(
        "Access granted: Custodian role verified."
    )

from django.contrib.auth.decorators import login_required



@login_required
def dashboard(request):
    roles = set(
        request.user.groups.values_list("name", flat=True)
    )

    if request.user.is_superuser:
        roles.add("System Administrator")

    context = {
        "role_text": ", ".join(sorted(roles))
                     if roles else "No role assigned",
        "is_requester": "Requester" in roles,
        "is_custodian": "Custodian" in roles,
        "is_approver": "Approver/Admin" in roles,
    }

    return render(
        request,
        "accounts/dashboard.html",
        context,
    )

@role_required("Approver/Admin")
def approver_test(request):
    return HttpResponse("Access granted: Approver role verified.")