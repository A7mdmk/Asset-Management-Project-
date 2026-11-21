
from django.urls import path

from .views import (
    ai_recommendations_view,
    approval_decision_view,
    approvals_view,
    my_requests_view,
    submit_request_view,
    transfer_management_view,
    arrange_transfer_view,
    dispatch_transfer_view,
    incoming_transfers_view,
    confirm_transfer_receipt_view,
    report_transfer_dispute_view,
    cancel_arranged_transfer_view,
    notifications_view,
    notification_mark_read_view,

)


urlpatterns = [
    path(
        "recommendations/",
        ai_recommendations_view,
        name="ai_recommendations",
    ),
    path(
        "my-requests/",
        my_requests_view,
        name="my_requests",
    ),
    path(
        "request/<uuid:asset_id>/",
        submit_request_view,
        name="submit_request",
    ),
    path(
        "approvals/",
        approvals_view,
        name="approvals",
    ),
    path(
        "approvals/<int:request_id>/<str:stage>/",
        approval_decision_view,
        name="approval_decision",
    ),
    path(
        "transfers/",
        transfer_management_view,
        name="transfer_management",
    ),
    path(
        "transfers/arrange/<int:reservation_id>/",
        arrange_transfer_view,
        name="arrange_transfer",
    ),
    path(
        "transfers/<int:transfer_id>/dispatch/",
        dispatch_transfer_view,
        name="dispatch_transfer",
    ),
    path(
    "transfers/incoming/",
    incoming_transfers_view,
    name="incoming_transfers",
    ),
    path(
    "transfers/<int:transfer_id>/receive/",
    confirm_transfer_receipt_view,
    name="confirm_transfer_receipt",
    ),
    path(
    "transfers/<int:transfer_id>/dispute/",
    report_transfer_dispute_view,
    name="report_transfer_dispute",
    ),
    path(
    "transfers/<int:transfer_id>/cancel/",
    cancel_arranged_transfer_view,
    name="cancel_arranged_transfer",
    ),
    path(
    "notifications/",
    notifications_view,
    name="notifications",
    ),
    path(
    "notifications/<int:notification_id>/read/",
    notification_mark_read_view,
    name="notification_mark_read",
    ),

]
