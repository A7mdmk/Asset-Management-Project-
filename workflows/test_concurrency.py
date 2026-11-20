
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from assets.models import Asset, Category, Department, StockBalance
from assets.services import register_asset
from .models import ResourceRequest, RequestApproval
from .services import submit_request, decide_request


class ConcurrentApprovalTests(TransactionTestCase):

    def setUp(self):
        User = get_user_model()

        requester_group, _ = Group.objects.get_or_create(
            name="Requester"
        )
        approver_group, _ = Group.objects.get_or_create(
            name="Approver/Admin"
        )

        self.requester = User.objects.create_user(
            username="concurrent_requester",
            password="TestPassword123!",
        )
        self.requester.groups.add(requester_group)

        self.approver_one = User.objects.create_user(
            username="concurrent_approver_one",
            password="TestPassword123!",
        )
        self.approver_one.groups.add(approver_group)

        self.approver_two = User.objects.create_user(
            username="concurrent_approver_two",
            password="TestPassword123!",
        )
        self.approver_two.groups.add(approver_group)

        self.custodian = User.objects.create_user(
            username="concurrent_custodian",
            password="TestPassword123!",
        )

        department = Department.objects.create(
            name="Engineering",
            code="CONC",
        )

        category = Category.objects.create(
            name="Computer Equipment",
        )

        self.asset = register_asset(
            name="Laboratory Laptops",
            category=category,
            department=department,
            custodian=self.custodian,
            location="Engineering Lab",
            tracking_mode=Asset.TrackingMode.LOT,
            quantity=5,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.PUBLISHED,
        )

        self.first_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            quantity=4,
            reason="First laboratory request",
        )

        self.second_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            quantity=4,
            reason="Second laboratory request",
        )

    def test_concurrent_approvals_do_not_overallocate_stock(self):
        if connections["default"].vendor != "mysql":
            self.skipTest("This test requires MySQL row locking.")

        barrier = Barrier(2)

        def approve(approver_id, request_id):
            close_old_connections()

            try:
                approver = get_user_model().objects.get(
                    pk=approver_id
                )

                # Both threads begin their approval attempts together.
                barrier.wait(timeout=10)

                try:
                    decide_request(
                        approver=approver,
                        request_id=request_id,
                        decision=RequestApproval.Decision.APPROVED,
                    )
                    return "approved"

                except ValidationError:
                    return "rejected"

            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                approve,
                self.approver_one.pk,
                self.first_request.pk,
            )
            second = executor.submit(
                approve,
                self.approver_two.pk,
                self.second_request.pk,
            )

            results = [
                first.result(timeout=30),
                second.result(timeout=30),
            ]

        self.assertEqual(results.count("approved"), 1)
        self.assertEqual(results.count("rejected"), 1)

        stock = StockBalance.objects.get(asset=self.asset)

        self.assertEqual(stock.free, 1)
        self.assertEqual(stock.held, 4)
        self.assertEqual(stock.total, 5)

        self.assertEqual(
            ResourceRequest.objects.filter(
                status=ResourceRequest.Status.APPROVED
            ).count(),
            1,
        )

        self.assertEqual(
            ResourceRequest.objects.filter(
                status=ResourceRequest.Status.PENDING
            ).count(),
            1,
        )

        self.assertEqual(RequestApproval.objects.count(), 1)
