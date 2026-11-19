from .views import custodian_test
from django.urls import path
from django.contrib.auth import views as auth_views
from .views import custodian_test, dashboard
from .views import custodian_test, dashboard, approver_test

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html"
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path("test-custodian/", custodian_test, name="test_custodian"),
    path("dashboard/", dashboard, name="dashboard"),
    path("test-approver/", approver_test, name="test_approver"),
]
