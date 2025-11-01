from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView,LoginView,
    UserViewSet,UserCreationRequestViewSet,
    DashboardViewSet,DashboardCreationRequestViewSet,
    PersonalDetailViewSet, AttendanceViewSet
)

router = DefaultRouter()
router.register('users',UserViewSet, basename='user')
router.register('user-requests',UserCreationRequestViewSet, basename='user-request')
router.register('dashboards',DashboardViewSet,basename='dashboard')
router.register('dashboard-requests', DashboardCreationRequestViewSet, basename='dashboard_request')
router.register(r"personal-details", PersonalDetailViewSet, basename="personaldetail")
router.register(r"attendances", AttendanceViewSet, basename="attendance")
urlpatterns = [
    path('register/',RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('', include(router.urls)),
]