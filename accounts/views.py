
from django.http import HttpResponse
from .permissions import role_required


@role_required("Custodian")
def custodian_test(request):
    return HttpResponse(
        "Access granted: Custodian role verified."
    )

from django.contrib.auth.decorators import login_required


@login_required
def dashboard(request):
    roles = list(
        request.user.groups.values_list("name", flat=True)
    )

    if request.user.is_superuser:
        roles.append("System Administrator")

    role_text = ", ".join(roles) if roles else "No role assigned"

    return HttpResponse(
        f"<h1>KU ResourceSavers Dashboard</h1>"
        f"<p>Welcome, {request.user.get_username()}!</p>"
        f"<p>Your role: {role_text}</p>"
    )
@role_required("Approver/Admin")
def approver_test(request):
    return HttpResponse("Access granted: Approver role verified.")