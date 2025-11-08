"""
URL configuration for ER_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from home.views import (
    RegisterView, LoginView,
    UserViewSet,
    UserCreationRequestViewSet,
    DashboardViewSet,
    DashboardCreationRequestViewSet,
    PersonalDetailViewSet,
    AttendanceViewSet,
)
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"user-requests", UserCreationRequestViewSet, basename="userrequest")
router.register(r"dashboards", DashboardViewSet, basename="dashboard")
router.register(r"dashboard-requests", DashboardCreationRequestViewSet, basename="dashboardrequest")
router.register(r"personal-details", PersonalDetailViewSet, basename="personaldetail")
router.register(r"attendances", AttendanceViewSet, basename="attendance")

urlpatterns = [
    path("admin/", admin.site.urls),
    # explicit register/login endpoints
    path("api/register/", RegisterView.as_view(), name="api-register"),
    path("api/login/", LoginView.as_view(), name="api-login"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/", include(router.urls)),
]