
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import (
    OperationalError,
    close_old_connections,
    connections,
)
from django.test import TransactionTestCase

from accounts.models import DepartmentApprover
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
        custodian_group, _ = Group.objects.get_or_create(
            name="Custodian"
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
        self.custodian.groups.add(custodian_group)

        department = Department.objects.create(
            name="Engineering",
            code="CONC",
        )

        # Authorize both destination approvers.
        DepartmentApprover.objects.create(
            department=department,
            user=self.approver_one,
            is_active=True,
        )

        DepartmentApprover.objects.create(
            department=department,
            user=self.approver_two,
            is_active=True,
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
            destination_department_id=department.pk,
            quantity=4,
            reason="First laboratory request",
        )

        self.second_request = submit_request(
            requester=self.requester,
            asset_id=self.asset.pk,
            destination_department_id=department.pk,
            quantity=4,
            reason="Second laboratory request",
        )

        # Stage 1: Both destinations accept their requests.
        decide_request(
            approver=self.approver_one,
            request_id=self.first_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        decide_request(
            approver=self.approver_two,
            request_id=self.second_request.pk,
            stage=RequestApproval.Stage.DESTINATION,
            decision=RequestApproval.Decision.APPROVED,
        )

        # Neither destination acceptance reserves stock.
        stock = StockBalance.objects.get(asset=self.asset)

        self.assertEqual(stock.free, 5)
        self.assertEqual(stock.held, 0)

    def test_concurrent_approvals_do_not_overallocate_stock(self):
        if connections["default"].vendor != "mysql":
            self.skipTest("This test requires MySQL row locking.")

        barrier = Barrier(2)

        def approve(request_id):
            close_old_connections()

            try:
                # Each worker obtains its own database connection.
                custodian = get_user_model().objects.get(
                    pk=self.custodian.pk
                )

                # Both source-release attempts start together.
                barrier.wait(timeout=10)

                try:
                    decide_request(
                        approver=custodian,
                        request_id=request_id,
                        stage=RequestApproval.Stage.SOURCE,
                        decision=RequestApproval.Decision.APPROVED,
                    )
                    return "approved"

                except ValidationError:
                    return "rejected"

                except OperationalError as exc:
                    # MySQL may select a transaction as a
                    # deadlock victim during concurrent locking.
                    mysql_code = (
                        exc.args[0] if exc.args else None
                    )

                    if mysql_code in (1205, 1213):
                        return "rejected"

                    raise

            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                approve,
                self.first_request.pk,
            )

            second = executor.submit(
                approve,
                self.second_request.pk,
            )

            results = [
                first.result(timeout=30),
                second.result(timeout=30),
            ]

        # Only one of the two requests can reserve four units.
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

        # Two destination approvals + one source release.
        self.assertEqual(
            RequestApproval.objects.filter(
                stage=RequestApproval.Stage.DESTINATION
            ).count(),
            2,
        )

        self.assertEqual(
            RequestApproval.objects.filter(
                stage=RequestApproval.Stage.SOURCE
            ).count(),
            1,
        )

        self.assertEqual(RequestApproval.objects.count(), 3)
