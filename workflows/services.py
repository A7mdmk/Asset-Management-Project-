
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import DepartmentApprover
from assets.models import Asset, Department, StockBalance

from .models import ResourceRequest, RequestApproval, Reservation


@transaction.atomic
def submit_request(
    *,
    requester,
    asset_id,
    destination_department_id,
    quantity,
    reason,
):
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

    if destination_department_id is None:
        raise ValidationError(
            "A destination department is required."
        )

    destination_department = Department.objects.get(
        pk=destination_department_id
    )

    if not destination_department.is_active:
        raise ValidationError(
            "Destination department must be active."
        )

    # Submission checks stock but does not reserve it.
    stock = StockBalance.objects.select_for_update().get(
        asset=asset
    )

    if stock.free < quantity:
        raise ValidationError(
            "Not enough free stock is available."
        )

    resource_request = ResourceRequest(
        asset=asset,
        requester=requester,
        destination_department=destination_department,
        quantity=quantity,
        reason=reason,
    )

    resource_request.full_clean()
    resource_request.save()

    return resource_request


@transaction.atomic
def decide_request(
    *,
    approver,
    request_id,
    stage,
    decision,
    comment="",
):
    if not approver.is_authenticated or not approver.is_active:
        raise ValidationError("An active account is required.")

    if stage not in (
        RequestApproval.Stage.DESTINATION,
        RequestApproval.Stage.SOURCE,
    ):
        raise ValidationError("Invalid approval stage.")

    if decision not in (
        RequestApproval.Decision.APPROVED,
        RequestApproval.Decision.REJECTED,
    ):
        raise ValidationError("Invalid approval decision.")

    resource_request = (
        ResourceRequest.objects.select_for_update()
        .select_related("asset", "destination_department")
        .get(pk=request_id)
    )

    if resource_request.status != ResourceRequest.Status.PENDING:
        raise ValidationError(
            "Only pending requests can be decided."
        )

    # Pending requests expire after 48 hours.
    if resource_request.expires_at <= timezone.now():
        resource_request.status = ResourceRequest.Status.EXPIRED
        resource_request.save(
            update_fields=["status", "updated_at"]
        )
        return resource_request

    if resource_request.requester_id == approver.pk:
        raise ValidationError(
            "Users cannot approve their own requests."
        )

    if not resource_request.destination_department_id:
        raise ValidationError(
            "The request has no destination department."
        )

    if not resource_request.destination_department.is_active:
        raise ValidationError(
            "The destination department is inactive."
        )

    previous_approvals = list(
        resource_request.approvals.order_by("created_at", "pk")
    )

    if any(
        item.stage == stage
        for item in previous_approvals
    ):
        raise ValidationError(
            "This approval stage has already been decided."
        )

    if any(
        item.approver_id == approver.pk
        for item in previous_approvals
    ):
        raise ValidationError(
            "Destination and source approvers must be different."
        )

    if decision == RequestApproval.Decision.REJECTED:
        if not comment.strip():
            raise ValidationError(
                "A reason is required when rejecting a request."
            )

    # STAGE 1: DESTINATION ACCEPTANCE
    if stage == RequestApproval.Stage.DESTINATION:
        if previous_approvals:
            raise ValidationError(
                "Destination acceptance must happen first."
            )

        if not approver.groups.filter(
            name="Approver/Admin"
        ).exists():
            raise ValidationError(
                "Destination approval role is required."
            )

        authorized = DepartmentApprover.objects.filter(
            user=approver,
            department_id=resource_request.destination_department_id,
            is_active=True,
        ).exists()

        if not authorized:
            raise ValidationError(
                "Not authorized for this destination department."
            )

        # Destination acceptance does not move stock
        # and does not create a reservation.

    # STAGE 2: SOURCE CUSTODIAN RELEASE
    elif stage == RequestApproval.Stage.SOURCE:
        destination_approval = next(
            (
                item
                for item in previous_approvals
                if (
                    item.stage == RequestApproval.Stage.DESTINATION
                    and item.decision
                    == RequestApproval.Decision.APPROVED
                )
            ),
            None,
        )

        if destination_approval is None:
            raise ValidationError(
                "Destination acceptance is required first."
            )

        asset = Asset.objects.select_for_update().get(
            pk=resource_request.asset_id
        )

        if asset.custodian_id != approver.pk:
            raise ValidationError(
                "Only the assigned source custodian "
                "can release this asset."
            )

        if not approver.groups.filter(
            name="Custodian"
        ).exists():
            raise ValidationError(
                "The source custodian role is required."
            )

        if decision == RequestApproval.Decision.APPROVED:
            if asset.publication != Asset.Publication.PUBLISHED:
                raise ValidationError(
                    "The asset is no longer published."
                )

            if asset.lifecycle != Asset.Lifecycle.ACTIVE:
                raise ValidationError(
                    "The asset is no longer active."
                )

            if asset.condition not in (
                Asset.Condition.GOOD,
                Asset.Condition.FAIR,
            ):
                raise ValidationError(
                    "The asset is no longer eligible."
                )

            stock = StockBalance.objects.select_for_update().get(
                asset=asset
            )

            if stock.free < resource_request.quantity:
                raise ValidationError(
                    "Insufficient free stock."
                )

            # Final source approval reserves stock exactly once.
            stock.free -= resource_request.quantity
            stock.held += resource_request.quantity

            stock.full_clean()
            stock.save(
                update_fields=["free", "held", "updated_at"]
            )

    # Record the approval decision.
    approval = RequestApproval(
        request=resource_request,
        approver=approver,
        stage=stage,
        decision=decision,
        comment=comment,
    )

    approval.full_clean()
    approval.save()

    # Create a reservation only after successful
    # final source approval.
    if (
        stage == RequestApproval.Stage.SOURCE
        and decision == RequestApproval.Decision.APPROVED
    ):
        reservation = Reservation(
            request=resource_request,
            source_approval=approval,
            quantity=resource_request.quantity,
            status=Reservation.Status.APPROVED,
        )

        reservation.full_clean()
        reservation.save()

    if decision == RequestApproval.Decision.REJECTED:
        resource_request.status = ResourceRequest.Status.REJECTED

    elif stage == RequestApproval.Stage.SOURCE:
        resource_request.status = ResourceRequest.Status.APPROVED

    resource_request.save(
        update_fields=["status", "updated_at"]
    )

    return resource_request


@transaction.atomic
def cancel_pending_request(*, requester, request_id):
    if not requester.is_authenticated or not requester.is_active:
        raise ValidationError("An active account is required.")

    resource_request = (
        ResourceRequest.objects.select_for_update()
        .get(pk=request_id)
    )

    if resource_request.requester_id != requester.pk:
        raise ValidationError(
            "Only the requester can cancel their pending request."
        )

    if resource_request.status != ResourceRequest.Status.PENDING:
        raise ValidationError(
            "Only pending requests can be cancelled."
        )

    resource_request.status = ResourceRequest.Status.CANCELLED

    resource_request.save(
        update_fields=["status", "updated_at"]
    )

    # Pending requests have no reservation,
    # so cancellation does not move stock.
    return resource_request

@transaction.atomic
def cancel_approved_reservation(
    *,
    actor,
    reservation_id,
    reason,
):
    if not actor.is_authenticated or not actor.is_active:
        raise ValidationError("An active account is required.")

    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError(
            "A cancellation reason is required."
        )

    # Lock the request first, consistently with approval operations.
    reservation_reference = Reservation.objects.get(
        pk=reservation_id
    )

    resource_request = (
        ResourceRequest.objects.select_for_update()
        .get(pk=reservation_reference.request_id)
    )

    asset = Asset.objects.select_for_update().get(
        pk=resource_request.asset_id
    )

    reservation = (
        Reservation.objects.select_for_update()
        .get(pk=reservation_id)
    )

    if actor.pk not in (
        resource_request.requester_id,
        asset.custodian_id,
    ):
        raise ValidationError(
            "Only the requester or assigned source custodian "
            "can cancel this reservation."
        )

    if (
        reservation.status != Reservation.Status.APPROVED
        or resource_request.status != ResourceRequest.Status.APPROVED
    ):
        raise ValidationError(
            "Only approved reservations that have not been "
            "converted to transfers can be cancelled."
        )

    stock = StockBalance.objects.select_for_update().get(
        asset=asset
    )

    if stock.held < reservation.quantity:
        raise ValidationError(
            "Insufficient held stock for cancellation."
        )

    # Release the reservation exactly once.
    stock.held -= reservation.quantity

    if (
        asset.condition in (
            Asset.Condition.GOOD,
            Asset.Condition.FAIR,
        )
        and asset.lifecycle == Asset.Lifecycle.ACTIVE
        and asset.publication == Asset.Publication.PUBLISHED
    ):
        stock.free += reservation.quantity
    else:
        stock.blocked += reservation.quantity

    stock.full_clean()
    stock.save(
        update_fields=[
            "free",
            "held",
            "blocked",
            "updated_at",
        ]
    )

    reservation.status = Reservation.Status.CANCELLED
    reservation.cancellation_reason = reason.strip()
    reservation.full_clean()
    reservation.save(
        update_fields=[
            "status",
            "cancellation_reason",
        ]
    )

    resource_request.status = ResourceRequest.Status.CANCELLED
    resource_request.save(
        update_fields=["status", "updated_at"]
    )

    return reservation
