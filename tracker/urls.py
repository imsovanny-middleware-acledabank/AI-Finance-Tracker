# tracker/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from tracker.views_api import (
    BudgetListAPIView,
    ExchangeRateAPIView,
    TransactionAddAPIView,
    TransactionDeleteAPIView,
    TransactionUpdateAPIView,
    UserListAPIView,
    TransactionViewAPIView,
    TransactionViewSet,
    dashboard_view,
)
from tracker.views_auth import (
    login_view,
    refresh_session,
    logout_view,
    request_otp,
    telegram_login_callback,
    user_view,
    verify_otp,
)
from tracker.views_spa import spa_index

router = DefaultRouter()
router.register(r"transactions", TransactionViewSet, basename="transaction")

urlpatterns = [
    path("", spa_index, name="dashboard"),
    path("legacy-dashboard/", dashboard_view, name="legacy_dashboard"),
    path("app/", spa_index, name="spa_index"),
    path("app/<path:path>", spa_index, name="spa_catchall"),
    path("api/rate/", ExchangeRateAPIView.as_view(), name="api_rate"),
    path("api/users/", UserListAPIView.as_view(), name="api_users_list"),
    path("api/budgets/", BudgetListAPIView.as_view(), name="api_budgets_list"),
    path("api/transactions/view/", TransactionViewAPIView.as_view(), name="api_transactions_view"),
    path("api/transactions/add/", TransactionAddAPIView.as_view(), name="api_transactions_add"),
    path("api/transactions/update/", TransactionUpdateAPIView.as_view(), name="api_transactions_update"),
    path("api/transactions/delete/", TransactionDeleteAPIView.as_view(), name="api_transactions_delete"),
    path("api/", include(router.urls)),
    path("login/", login_view, name="login"),
    path("auth/callback/", telegram_login_callback, name="telegram_callback"),
    path("auth/user/", user_view, name="auth_user"),
    path("auth/refresh/", refresh_session, name="auth_refresh"),
    path("auth/logout/", logout_view, name="auth_logout"),
    path("auth/request-otp/", request_otp, name="request_otp"),
    path("auth/verify-otp/", verify_otp, name="verify_otp"),
]
