# tracker/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from tracker.views_api import TransactionViewSet, dashboard_view
from tracker.views_auth import (
    login_view, telegram_login_callback, user_view, logout_view,
    request_otp, verify_otp
)

router = DefaultRouter()
router.register(r'transactions', TransactionViewSet, basename='transaction')

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    path('api/', include(router.urls)),
    path('login/', login_view, name='login'),
    path('auth/callback/', telegram_login_callback, name='telegram_callback'),
    path('auth/user/', user_view, name='auth_user'),
    path('auth/logout/', logout_view, name='auth_logout'),
    path('auth/request-otp/', request_otp, name='request_otp'),
    path('auth/verify-otp/', verify_otp, name='verify_otp'),
]
