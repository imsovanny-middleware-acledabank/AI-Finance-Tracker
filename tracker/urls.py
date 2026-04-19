# tracker/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from tracker.views_api import TransactionViewSet, dashboard_view
from tracker.views_auth import login_page, authenticate_telegram, logout, user_info

router = DefaultRouter()
router.register(r'transactions', TransactionViewSet, basename='transaction')

urlpatterns = [
    path('login/', login_page, name='login'),
    path('auth/telegram/', authenticate_telegram, name='auth_telegram'),
    path('auth/logout/', logout, name='logout'),
    path('auth/user/', user_info, name='user_info'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('', dashboard_view, name='dashboard_home'),
    path('api/', include(router.urls)),
]
