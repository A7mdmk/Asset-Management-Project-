
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from assets.models import Asset, Category, Department, StockBalance
from .models import ResourceRequest


class SubmitRequestViewTests(TestCase):

    def setUp(self):
        User = get_user_model()

        requester_group, _ = Group.objects.get_or_create(
            name="Requester"
        )

        self.requester = User.objects.create_user(
            username="submit_view_requester",
            password="TestPassword123!",
        )
        self.requester.groups.add(requester_group)

        self.other_user = User.objects.create_user(
            username="submit_view_other",
            password="TestPassword123!",
        )

        self.department = Department.objects.create(
            name="Submit View Department",
            code="SUBVIEW",
            is_active=True,
        )

        self.category = Category.objects.create(
            name="Submit View Equipment",
        )

        self.asset = Asset.objects.create(
            name="Submit View Laptop",
            asset_tag="SUBVIEW-001",
            category=self.category,
            department=self.department,
            custodian=self.other_user,
            location="Computer Lab",
            tracking_mode=Asset.TrackingMode.INDIVIDUAL,
            quantity=1,
            condition=Asset.Condition.GOOD,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=Asset.Publication.PUBLISHED,
        )

        StockBalance.objects.create(
            asset=self.asset,
            free=1,
        )

        self.url = reverse(
            "submit_request",
            args=[self.asset.pk],
        )

        self.valid_data = {
            "destination_department": str(self.department.pk),
            "quantity": "1",
            "reason": "Needed for a laboratory project.",
        }

    def test_login_required(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_non_requester_is_forbidden(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_requester_can_open_form(self):
        self.client.force_login(self.requester)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "workflows/submit_request.html",
        )

    def test_valid_submission_creates_request(self):
        self.client.force_login(self.requester)

        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertRedirects(
            response,
            reverse("my_requests"),
        )

        resource_request = ResourceRequest.objects.get(
            requester=self.requester
        )

        self.assertEqual(
            resource_request.asset,
            self.asset,
        )
        self.assertEqual(
            resource_request.quantity,
            1,
        )
        self.assertEqual(
            resource_request.status,
            ResourceRequest.Status.PENDING,
        )

    def test_invalid_quantity_shows_error(self):
        self.client.force_login(self.requester)

        data = {
            **self.valid_data,
            "quantity": "0",
        }

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            ResourceRequest.objects.filter(
                requester=self.requester
            ).exists()
        )
        self.assertTrue(response.context["form"].errors)

    def test_service_validation_error_is_displayed(self):
        self.client.force_login(self.requester)

        with patch(
            "workflows.views.submit_request",
            side_effect=ValidationError(
                "Not enough free stock is available."
            ),
        ):
            response = self.client.post(
                self.url,
                self.valid_data,
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Not enough free stock is available.",
        )

    def test_unpublished_asset_cannot_be_requested(self):
        self.asset.publication = Asset.Publication.DRAFT
        self.asset.save(update_fields=["publication"])

        self.client.force_login(self.requester)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_unavailable_asset_cannot_be_requested(self):
        stock = self.asset.stock
        stock.free = 0
        stock.in_use = 1
        stock.save(update_fields=["free", "in_use"])

        self.client.force_login(self.requester)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

