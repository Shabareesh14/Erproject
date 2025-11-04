from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView,
    LoginView,
    UserViewSet,
    UserCreationRequestViewSet,
    DashboardViewSet,
    DashboardCreationRequestViewSet,
    DepartmentViewSet,
    SubjectViewSet,
    AttendanceViewSet,
    MarksViewSet,
    LeaveRequestViewSet,
    AnnouncementViewSet,
    SystemSettingsViewSet,
    SuperAdminDashboardView,
    HODDashboardView,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("user-requests", UserCreationRequestViewSet, basename="user-request")
router.register("dashboards", DashboardViewSet, basename="dashboard")
router.register(
    "dashboard-requests", DashboardCreationRequestViewSet, basename="dashboard_request"
)

# New endpoints
router.register("departments", DepartmentViewSet, basename="department")
router.register("subjects", SubjectViewSet, basename="subject")
router.register("attendance", AttendanceViewSet, basename="attendance")
router.register("marks", MarksViewSet, basename="marks")
router.register("leave-requests", LeaveRequestViewSet, basename="leave-request")
router.register("announcements", AnnouncementViewSet, basename="announcement")
router.register("settings", SystemSettingsViewSet, basename="settings")

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    # Dashboard endpoints
    path(
        "dashboard/superadmin/",
        SuperAdminDashboardView.as_view(),
        name="superadmin-dashboard",
    ),
    path("dashboard/hod/", HODDashboardView.as_view(), name="hod-dashboard"),
    path("", include(router.urls)),
]