
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import (
    Asset,
    Category,
    Department,
    StockMovement,
)
from .services import register_asset


class StockMovementAdminTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.admin_user = User.objects.create_superuser(
            username="stock_audit_admin",
            email="stock_audit_admin@example.com",
            password="TestPassword123!",
        )

        self.custodian = User.objects.create_user(
            username="stock_audit_custodian",
            password="TestPassword123!",
        )

        self.department = Department.objects.create(
            name="Audit Admin Department",
            code="AUDIT-ADM",
        )

        self.category = Category.objects.create(
            name="Audit Admin Equipment",
        )

        self.asset = register_asset(
            name="Audit Admin Laptop",
            asset_tag="AUDIT-ADM-001",
            category=self.category,
            department=self.department,
            custodian=self.custodian,
            location="Computer Lab",
            tracking_mode=Asset.TrackingMode.INDIVIDUAL,
            quantity=1,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.DRAFT,
        )

        self.movement = StockMovement.objects.get(
            asset=self.asset
        )

        self.client.force_login(self.admin_user)

    # TEST 1: ADMIN CAN VIEW MOVEMENT HISTORY

    def test_admin_can_view_movement_history(self):
        url = reverse(
            "admin:assets_stockmovement_changelist"
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Audit Admin Laptop",
        )

    # TEST 2: ADMIN CANNOT ADD MOVEMENTS

    def test_admin_cannot_add_stock_movement(self):
        url = reverse(
            "admin:assets_stockmovement_add"
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

        self.assertEqual(
            StockMovement.objects.filter(
                asset=self.asset
            ).count(),
            1,
        )

    # TEST 3: ADMIN CANNOT EDIT MOVEMENTS


    # TEST 3: ADMIN CAN VIEW BUT CANNOT EDIT MOVEMENTS

    def test_admin_cannot_edit_stock_movement(self):
        url = reverse(
            "admin:assets_stockmovement_change",
            args=[self.movement.pk],
        )

        # Django allows a read-only detail page.
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Verify that submitting changes is forbidden.
        response = self.client.post(
            url,
            {
                "movement_type": (
                    StockMovement.MovementType.DISPATCH
                ),
                "quantity": 999,
                "source": StockMovement.Bucket.HELD,
                "destination": (
                    StockMovement.Bucket.IN_TRANSIT
                ),
            },
        )

        self.assertEqual(response.status_code, 403)

        self.movement.refresh_from_db()

        self.assertEqual(
            self.movement.movement_type,
            StockMovement.MovementType.REGISTRATION,
        )

        self.assertEqual(self.movement.quantity, 1)
        self.assertEqual(self.movement.source, "")
        self.assertEqual(
            self.movement.destination,
            StockMovement.Bucket.FREE,
        )


    # TEST 4: ADMIN CANNOT DELETE MOVEMENTS

    def test_admin_cannot_delete_stock_movement(self):
        url = reverse(
            "admin:assets_stockmovement_delete",
            args=[self.movement.pk],
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

        self.assertTrue(
            StockMovement.objects.filter(
                pk=self.movement.pk
            ).exists()
        )
