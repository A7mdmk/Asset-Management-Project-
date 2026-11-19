
from django.core.exceptions import ValidationError
from django.db import transaction

from assets.models import Asset
from .models import ResourceRequest, RequestApproval


@transaction.atomic
def submit_request(*, requester, asset_id, quantity, reason):
    if not requester.is_authenticated or not requester.is_active:
        raise ValidationError("An active account is required.")

    if not requester.groups.filter(name="Requester").exists():
        raise ValidationError("Only Requesters can submit requests.")

    asset = Asset.objects.select_for_update().get(pk=asset_id)

    if asset.publication != Asset.Publication.PUBLISHED:
        raise ValidationError("The asset must be published.")

    if asset.lifecycle != Asset.Lifecycle.ACTIVE:
        raise ValidationError("The asset must be active.")

    if asset.condition not in (
        Asset.Condition.GOOD,
        Asset.Condition.FAIR,
    ):
        raise ValidationError("This asset is not eligible for requests.")

    if not isinstance(quantity, int) or isinstance(quantity, bool):
        raise ValidationError("Quantity must be a whole number.")

    if quantity < 1:
        raise ValidationError("Quantity must be at least 1.")

    if asset.tracking_mode == Asset.TrackingMode.INDIVIDUAL:
        if quantity != 1:
            raise ValidationError(
                "Individual assets can only be requested one at a time."
            )

    if asset.stock.free < quantity:
        raise ValidationError("Not enough free stock is available.")

    resource_request = ResourceRequest(
        asset=asset,
        requester=requester,
        quantity=quantity,
        reason=reason,
    )

    resource_request.full_clean()
    resource_request.save()

    return resource_request

@transaction.atomic
def decide_request(*, approver, request_id, decision, comment=""):
    if not approver.is_authenticated or not approver.is_active:
        raise ValidationError("An active account is required.")

    if not (
        approver.is_superuser
        or approver.groups.filter(name="Approver/Admin").exists()
    ):
        raise ValidationError("Only authorized approvers can decide requests.")

    if decision not in (
        RequestApproval.Decision.APPROVED,
        RequestApproval.Decision.REJECTED,
    ):
        raise ValidationError("Invalid approval decision.")

    resource_request = (
        ResourceRequest.objects.select_for_update()
        .select_related("asset")
        .get(pk=request_id)
    )

    if resource_request.status != ResourceRequest.Status.PENDING:
        raise ValidationError("Only pending requests can be decided.")

    if resource_request.requester_id == approver.pk:
        raise ValidationError("You cannot approve your own request.")

    if resource_request.approvals.exists():
        raise ValidationError("This request already has a decision.")

    if decision == RequestApproval.Decision.APPROVED:
        stock = (
            resource_request.asset.stock.__class__.objects
            .select_for_update()
            .get(asset_id=resource_request.asset_id)
        )

        if stock.free < resource_request.quantity:
            raise ValidationError("Insufficient free stock.")

        stock.free -= resource_request.quantity
        stock.held += resource_request.quantity
        stock.full_clean()
        stock.save(update_fields=["free", "held", "updated_at"])

        resource_request.status = ResourceRequest.Status.APPROVED

    else:
        resource_request.status = ResourceRequest.Status.REJECTED

    approval = RequestApproval(
        request=resource_request,
        approver=approver,
        decision=decision,
        comment=comment,
    )
    approval.full_clean()
    approval.save()

    resource_request.save(update_fields=["status", "updated_at"])

    return resource_request
