# tracker/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from tracker.views_api import (
    ExchangeRateAPIView,
    TransactionAddAPIView,
    TransactionDeleteAPIView,
    TransactionUpdateAPIView,
    TransactionViewAPIView,
    TransactionViewSet,
    dashboard_view,
)
from tracker.views_auth import (
    login_view,
    logout_view,
    request_otp,
    telegram_login_callback,
    user_view,
    verify_otp,
)

router = DefaultRouter()
router.register(r"transactions", TransactionViewSet, basename="transaction")

urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("api/rate/", ExchangeRateAPIView.as_view(), name="api_rate"),
    path("api/transactions/view/", TransactionViewAPIView.as_view(), name="api_transactions_view"),
    path("api/transactions/add/", TransactionAddAPIView.as_view(), name="api_transactions_add"),
    path("api/transactions/update/", TransactionUpdateAPIView.as_view(), name="api_transactions_update"),
    path("api/transactions/delete/", TransactionDeleteAPIView.as_view(), name="api_transactions_delete"),
    path("api/", include(router.urls)),
    path("login/", login_view, name="login"),
    path("auth/callback/", telegram_login_callback, name="telegram_callback"),
    path("auth/user/", user_view, name="auth_user"),
    path("auth/logout/", logout_view, name="auth_logout"),
    path("auth/request-otp/", request_otp, name="request_otp"),
    path("auth/verify-otp/", verify_otp, name="verify_otp"),
]
