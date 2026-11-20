
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import ResourceRequest


class MyRequestsViewTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.requester_group, _ = Group.objects.get_or_create(
            name="Requester"
        )

        self.requester = User.objects.create_user(
            username="my_requests_user",
            password="TestPassword123!",
        )
        self.requester.groups.add(self.requester_group)

        self.other_user = User.objects.create_user(
            username="other_requests_user",
            password="TestPassword123!",
        )

        self.url = reverse("my_requests")

    # TEST 1: LOGIN REQUIRED

    def test_login_required(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    # TEST 2: REQUESTER CAN VIEW PAGE

    def test_requester_can_view_page(self):
        self.client.force_login(self.requester)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "workflows/my_requests.html",
        )

    # TEST 3: NON-REQUESTER CANNOT ACCESS PAGE

    def test_non_requester_is_forbidden(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    # TEST 4: REQUESTS ARE FILTERED BY CURRENT USER

    @patch("workflows.views.ResourceRequest.objects")
    def test_requests_filtered_by_logged_in_user(self, mock_objects):
        self.client.force_login(self.requester)

        mock_queryset = mock_objects.filter.return_value
        mock_queryset.select_related.return_value = mock_queryset
        mock_queryset.order_by.return_value = (
            ResourceRequest.objects.none()
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        mock_objects.filter.assert_called_once_with(
            requester=self.requester
        )

    # TEST 5: INVALID STATUS FILTER IS IGNORED

    def test_invalid_status_filter(self):
        self.client.force_login(self.requester)

        response = self.client.get(
            self.url,
            {"status": "InvalidStatus"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["selected_status"],
            "",
        )

    # TEST 6: VALID STATUS FILTER IS ACCEPTED

    def test_valid_status_filter(self):
        self.client.force_login(self.requester)

        response = self.client.get(
            self.url,
            {"status": ResourceRequest.Status.PENDING},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["selected_status"],
            ResourceRequest.Status.PENDING,
        )
