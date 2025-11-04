from rest_framework import status, viewsets, generics
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from django.db.models import Count, Q, Avg
from datetime import datetime

from .models import (
    User,
    UserCreationRequest,
    Dashboard,
    DashboardCreationRequest,
    Department,
    Subject,
    Attendance,
    Marks,
    LeaveRequest,
    Announcement,
    SystemSettings,
)
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    LoginSerializer,
    UserCreationRequestSerializer,
    ApproveUserCreationSerializer,
    DashboardSerializer,
    DashboardCreationRequestSerializer,
    ApproveDashboardCreationSerializer,
    DepartmentSerializer,
    SubjectSerializer,
    AttendanceSerializer,
    MarksSerializer,
    LeaveRequestSerializer,
    ApproveLeaveRequestSerializer,
    AnnouncementSerializer,
    SystemSettingsSerializer,
    DashboardOverviewSerializer,
    HODDashboardSerializer,
    AttendanceSummarySerializer,
)
from .permissions import IsSuperAdmin, IsAdminOrSuperAdmin, IsFacultyOrAbove


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


# ===================== AUTH VIEWS =====================


class RegisterView(generics.CreateAPIView):
    """Public registration - creates STUDENT accounts only"""

    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data["role"] = "STUDENT"
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = get_tokens_for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": tokens,
                "message": "Student registered successfully",
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(generics.GenericAPIView):
    """Login for all user types"""

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data
        tokens = get_tokens_for_user(user)
        return Response(
            {"user": UserSerializer(user).data, "tokens": tokens},
            status=status.HTTP_200_OK,
        )


# ===================== USER MANAGEMENT =====================


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    User management with role-based filtering:
    - SUPERADMIN: sees all users
    - ADMIN: sees users in their department
    - FACULTY: sees students in their department
    - STUDENT: sees only themselves
    """

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "SUPERADMIN":
            return User.objects.all()
        elif user.role == "ADMIN":
            # HOD sees all users in their department
            return User.objects.filter(
                Q(department=user.department) | Q(id=user.id)
            ).filter(role__in=["FACULTY", "STUDENT", "ADMIN"])
        elif user.role == "FACULTY":
            # Faculty sees students in their department
            return User.objects.filter(department=user.department, role="STUDENT")
        else:
            # Students see only themselves
            return User.objects.filter(id=user.id)

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class UserCreationRequestViewSet(viewsets.ModelViewSet):
    """
    User creation with approval workflow:
    - SUPERADMIN: creates users directly
    - ADMIN: requests FACULTY/STUDENT (needs SUPERADMIN approval for FACULTY)
    - FACULTY: requests STUDENT (needs ADMIN approval)
    - STUDENT: cannot create users
    """

    serializer_class = UserCreationRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "SUPERADMIN":
            return UserCreationRequest.objects.all()
        elif user.role == "ADMIN":
            return UserCreationRequest.objects.filter(
                requested_by__role__in=["FACULTY", "ADMIN"]
            )
        elif user.role == "FACULTY":
            return UserCreationRequest.objects.filter(requested_by=user)
        return UserCreationRequest.objects.none()

    def create(self, request, *args, **kwargs):
        user = request.user

        # Validation
        if not user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if user.role == "STUDENT":
            return Response(
                {"error": "Students cannot create users"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # SUPERADMIN creates users directly (no approval needed)
        if user.role == "SUPERADMIN":
            try:
                user_serializer = RegisterSerializer(
                    data=request.data, context={"request": request}
                )
                user_serializer.is_valid(raise_exception=True)
                new_user = user_serializer.save()
                return Response(
                    {
                        "message": "User created directly by SUPERADMIN",
                        "user": UserSerializer(new_user).data,
                    },
                    status=status.HTTP_201_CREATED,
                )
            except Exception as e:
                return Response(
                    {"error": f"Failed to create user: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # FACULTY/ADMIN create request (needs approval)
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            request_obj = serializer.save()
            approver = "ADMIN" if user.role == "FACULTY" else "SUPERADMIN"
            return Response(
                {
                    "message": f"Request submitted. Waiting for {approver} approval",
                    "request": UserCreationRequestSerializer(request_obj).data,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to create request: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve or reject user creation request"""
        try:
            request_obj = self.get_object()
            user = request.user

            if request_obj.status != "PENDING":
                return Response(
                    {"error": f"Request already {request_obj.status.lower()}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Permission validation
            if request_obj.requested_by.role == "FACULTY" and user.role not in [
                "ADMIN",
                "SUPERADMIN",
            ]:
                return Response(
                    {"error": "Only ADMIN/SUPERADMIN can approve FACULTY requests"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if request_obj.requested_by.role == "ADMIN" and user.role != "SUPERADMIN":
                return Response(
                    {"error": "Only SUPERADMIN can approve ADMIN requests"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            serializer = ApproveUserCreationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            with transaction.atomic():
                if serializer.validated_data["approve"]:
                    request_obj.status = "APPROVED"
                    request_obj.approved_by = user
                    request_obj.save()
                    new_user = User.objects.create(
                        username=request_obj.username,
                        email=request_obj.email,
                        password=request_obj.password,
                        role=request_obj.role,
                        department=request_obj.department,
                    )
                    return Response(
                        {
                            "message": "Request approved",
                            "user": UserSerializer(new_user).data,
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    request_obj.status = "REJECTED"
                    request_obj.approved_by = user
                    request_obj.rejection_reason = serializer.validated_data.get(
                        "rejection_reason"
                    )
                    request_obj.save()
                    return Response(
                        {"message": "Request rejected"}, status=status.HTTP_200_OK
                    )
        except Exception as e:
            return Response(
                {"error": f"Failed to process approval: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def pending(self, request):
        """Get pending requests based on user role"""
        user = request.user
        if user.role == "SUPERADMIN":
            pending = UserCreationRequest.objects.filter(status="PENDING")
        elif user.role == "ADMIN":
            pending = UserCreationRequest.objects.filter(
                status="PENDING", requested_by__role="FACULTY"
            )
        else:
            pending = UserCreationRequest.objects.none()
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)


# ===================== DASHBOARD MANAGEMENT =====================


class DashboardViewSet(viewsets.ModelViewSet):
    """Dashboard CRUD - only SUPERADMIN can modify"""

    serializer_class = DashboardSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Dashboard.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsSuperAdmin()]
        return [IsAuthenticated()]


class DashboardCreationRequestViewSet(viewsets.ModelViewSet):
    """
    Dashboard creation with approval:
    - SUPERADMIN: creates directly
    - ADMIN: requests (needs SUPERADMIN approval)
    """

    serializer_class = DashboardCreationRequestSerializer
    permission_classes = [IsAdminOrSuperAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == "SUPERADMIN":
            return DashboardCreationRequest.objects.all()
        return DashboardCreationRequest.objects.filter(requested_by=user)

    def create(self, request, *args, **kwargs):
        if request.user.role not in ["ADMIN", "SUPERADMIN"]:
            return Response(
                {"error": "Only ADMIN/SUPERADMIN can create dashboards"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_obj = serializer.save()

        if request.user.role == "SUPERADMIN":
            return Response(
                {
                    "message": "Dashboard created by SUPERADMIN",
                    "dashboard": DashboardSerializer(request_obj.dashboard).data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {
                "message": "Request submitted. Waiting for SUPERADMIN approval",
                "request": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def approve(self, request, pk=None):
        """Approve or reject dashboard creation request"""
        request_obj = self.get_object()

        if request_obj.status != "PENDING":
            return Response(
                {"error": f"Already {request_obj.status.lower()}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ApproveDashboardCreationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            if serializer.validated_data["approve"]:
                request_obj.status = "APPROVED"
                request_obj.approved_by = request.user
                dashboard = Dashboard.objects.create(
                    title=request_obj.title,
                    description=request_obj.description,
                    created_by=request_obj.requested_by,
                )
                request_obj.dashboard = dashboard
                request_obj.save()
                return Response(
                    {
                        "message": "Dashboard approved",
                        "dashboard": DashboardSerializer(dashboard).data,
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                request_obj.status = "REJECTED"
                request_obj.approved_by = request.user
                request_obj.rejection_reason = serializer.validated_data.get(
                    "rejection_reason"
                )
                request_obj.save()
                return Response(
                    {"message": "Request rejected"}, status=status.HTTP_200_OK
                )

    @action(detail=False, methods=["get"], permission_classes=[IsSuperAdmin])
    def pending(self, request):
        """Get pending dashboard requests"""
        pending = DashboardCreationRequest.objects.filter(status="PENDING")
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)


# ===================== DEPARTMENT MANAGEMENT =====================


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    Department management:
    - SUPERADMIN: full CRUD access
    - ADMIN: view their own department
    - Others: view active departments
    """

    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "SUPERADMIN":
            return Department.objects.all()
        elif user.role == "ADMIN":
            return Department.objects.filter(Q(hod=user) | Q(is_active=True))
        return Department.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsSuperAdmin()]
        return [IsAuthenticated()]

    @action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def assign_hod(self, request, pk=None):
        """Assign HOD to department"""
        department = self.get_object()
        hod_id = request.data.get("hod_id")

        try:
            hod = User.objects.get(id=hod_id, role="ADMIN")
            department.hod = hod
            department.save()
            return Response(
                {"message": "HOD assigned successfully"}, status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid HOD or user is not an ADMIN"},
                status=status.HTTP_400_BAD_REQUEST,
            )


# ===================== SUBJECT MANAGEMENT =====================


class SubjectViewSet(viewsets.ModelViewSet):
    """
    Subject management:
    - SUPERADMIN: all subjects
    - ADMIN: subjects in their department
    - FACULTY: subjects they teach
    - STUDENT: subjects in their department
    """

    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "SUPERADMIN":
            return Subject.objects.all()
        elif user.role == "ADMIN":
            return Subject.objects.filter(department=user.department)
        elif user.role == "FACULTY":
            return Subject.objects.filter(
                Q(department=user.department) | Q(assigned_faculty=user)
            )
        return Subject.objects.filter(department=user.department, is_active=True)

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminOrSuperAdmin()]
        return [IsAuthenticated()]

    @action(detail=True, methods=["post"], permission_classes=[IsAdminOrSuperAdmin])
    def assign_faculty(self, request, pk=None):
        """Assign faculty members to subject"""
        subject = self.get_object()
        faculty_ids = request.data.get("faculty_ids", [])

        try:
            faculty = User.objects.filter(
                id__in=faculty_ids, role="FACULTY", department=subject.department
            )
            subject.assigned_faculty.set(faculty)
            return Response(
                {"message": "Faculty assigned successfully"}, status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ===================== ATTENDANCE MANAGEMENT =====================


class AttendanceViewSet(viewsets.ModelViewSet):
    """
    Attendance management:
    - SUPERADMIN: all attendance
    - ADMIN: department attendance
    - FACULTY: subjects they teach
    - STUDENT: their own attendance
    """

    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "SUPERADMIN":
            return Attendance.objects.all()
        elif user.role == "ADMIN":
            return Attendance.objects.filter(student__department=user.department)
        elif user.role == "FACULTY":
            return Attendance.objects.filter(subject__assigned_faculty=user)
        return Attendance.objects.filter(student=user)

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update"]:
            return [IsFacultyOrAbove()]
        return [IsAuthenticated()]

    @action(detail=False, methods=["get"])
    def student_summary(self, request):
        """Get attendance summary for a student"""
        student_id = request.query_params.get("student_id")
        subject_id = request.query_params.get("subject_id")

        queryset = self.get_queryset()

        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)

        total = queryset.count()
        present = queryset.filter(status="PRESENT").count()
        absent = queryset.filter(status="ABSENT").count()

        percentage = (present / total * 100) if total > 0 else 0

        return Response(
            {
                "total_classes": total,
                "present": present,
                "absent": absent,
                "percentage": round(percentage, 2),
            }
        )


# ===================== MARKS MANAGEMENT =====================


class MarksViewSet(viewsets.ModelViewSet):
    """
    Marks management:
    - SUPERADMIN: all marks
    - ADMIN: department marks
    - FACULTY: marks they entered
    - STUDENT: their own marks
    """

    serializer_class = MarksSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "SUPERADMIN":
            return Marks.objects.all()
        elif user.role == "ADMIN":
            return Marks.objects.filter(student__department=user.department)
        elif user.role == "FACULTY":
            return Marks.objects.filter(faculty=user)
        return Marks.objects.filter(student=user)

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update"]:
            return [IsFacultyOrAbove()]
        return [IsAuthenticated()]

    @action(detail=False, methods=["get"])
    def student_summary(self, request):
        """Get marks summary for a student"""
        student_id = request.query_params.get("student_id")

        if not student_id:
            return Response(
                {"error": "student_id required"}, status=status.HTTP_400_BAD_REQUEST
            )

        marks = self.get_queryset().filter(student_id=student_id)

        summary = marks.values("subject__name", "subject__code").annotate(
            total_marks=Count("id"),
            avg_percentage=Avg("marks_obtained") / Avg("max_marks") * 100,
        )

        return Response(summary)


# ===================== LEAVE MANAGEMENT =====================


class LeaveRequestViewSet(viewsets.ModelViewSet):
    """
    Leave request management:
    - STUDENT: can create requests
    - ADMIN/SUPERADMIN: can approve/reject
    """

    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "SUPERADMIN":
            return LeaveRequest.objects.all()
        elif user.role == "ADMIN":
            return LeaveRequest.objects.filter(student__department=user.department)
        elif user.role == "FACULTY":
            return LeaveRequest.objects.filter(student__department=user.department)
        return LeaveRequest.objects.filter(student=user)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminOrSuperAdmin])
    def approve(self, request, pk=None):
        """Approve or reject leave request"""
        leave_request = self.get_object()

        if leave_request.status != "PENDING":
            return Response(
                {"error": f"Request already {leave_request.status.lower()}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ApproveLeaveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data["approve"]:
            leave_request.status = "APPROVED"
            leave_request.approved_by = request.user
            leave_request.save()
            return Response(
                {"message": "Leave request approved"}, status=status.HTTP_200_OK
            )
        else:
            leave_request.status = "REJECTED"
            leave_request.approved_by = request.user
            leave_request.rejection_reason = serializer.validated_data.get(
                "rejection_reason", ""
            )
            leave_request.save()
            return Response(
                {"message": "Leave request rejected"}, status=status.HTTP_200_OK
            )

    @action(detail=False, methods=["get"])
    def pending(self, request):
        """Get pending leave requests"""
        user = request.user
        if user.role in ["ADMIN", "SUPERADMIN"]:
            if user.role == "ADMIN":
                pending = LeaveRequest.objects.filter(
                    status="PENDING", student__department=user.department
                )
            else:
                pending = LeaveRequest.objects.filter(status="PENDING")

            serializer = self.get_serializer(pending, many=True)
            return Response(serializer.data)

        return Response(
            {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
        )


# ===================== ANNOUNCEMENTS =====================


class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    Announcements with role-based filtering:
    - Filters based on target_audience and department
    """

    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Announcement.objects.filter(is_active=True)

        if user.role == "SUPERADMIN":
            return queryset
        elif user.role == "ADMIN":
            return queryset.filter(
                Q(target_audience="ALL")
                | Q(target_audience="ADMIN")
                | Q(target_audience="DEPARTMENT", department=user.department)
            )
        elif user.role == "FACULTY":
            return queryset.filter(
                Q(target_audience="ALL")
                | Q(target_audience="FACULTY")
                | Q(target_audience="DEPARTMENT", department=user.department)
            )
        else:
            return queryset.filter(
                Q(target_audience="ALL")
                | Q(target_audience="STUDENT")
                | Q(target_audience="DEPARTMENT", department=user.department)
            )

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsFacultyOrAbove()]
        return [IsAuthenticated()]


# ===================== SYSTEM SETTINGS =====================


class SystemSettingsViewSet(viewsets.ModelViewSet):
    """System settings - only SUPERADMIN can modify"""

    serializer_class = SystemSettingsSerializer
    permission_classes = [IsSuperAdmin]

    def get_queryset(self):
        return SystemSettings.objects.all()

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def current(self, request):
        """Get current settings (all users can view)"""
        settings = SystemSettings.get_settings()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)


# ===================== DASHBOARD & REPORTS =====================


class SuperAdminDashboardView(generics.GenericAPIView):
    """Dashboard for SUPERADMIN with system-wide statistics"""

    permission_classes = [IsSuperAdmin]

    def get(self, request):
        departments = Department.objects.aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(is_active=True)),
            with_hod=Count("id", filter=Q(hod__isnull=False)),
        )

        users = User.objects.aggregate(
            total=Count("id"),
            superadmins=Count("id", filter=Q(role="SUPERADMIN")),
            admins=Count("id", filter=Q(role="ADMIN")),
            faculty=Count("id", filter=Q(role="FACULTY")),
            students=Count("id", filter=Q(role="STUDENT")),
        )

        data = {
            "departments": {
                "total_departments": departments["total"],
                "active_departments": departments["active"],
                "departments_with_hod": departments["with_hod"],
            },
            "users": {
                "total_users": users["total"],
                "superadmins": users["superadmins"],
                "admins": users["admins"],
                "faculty": users["faculty"],
                "students": users["students"],
            },
            "pending_user_requests": UserCreationRequest.objects.filter(
                status="PENDING"
            ).count(),
            "pending_dashboard_requests": DashboardCreationRequest.objects.filter(
                status="PENDING"
            ).count(),
            "total_subjects": Subject.objects.count(),
            "total_announcements": Announcement.objects.filter(is_active=True).count(),
        }

        return Response(data)


class HODDashboardView(generics.GenericAPIView):
    """Dashboard for HOD (ADMIN) with department statistics"""

    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request):
        user = request.user

        if user.role != "ADMIN":
            return Response(
                {"error": "Only HODs can access this dashboard"},
                status=status.HTTP_403_FORBIDDEN,
            )

        department = user.department

        data = {
            "department_name": department.name if department else "N/A",
            "total_faculty": (
                User.objects.filter(department=department, role="FACULTY").count()
                if department
                else 0
            ),
            "total_students": (
                User.objects.filter(department=department, role="STUDENT").count()
                if department
                else 0
            ),
            "pending_leave_requests": (
                LeaveRequest.objects.filter(
                    student__department=department, status="PENDING"
                ).count()
                if department
                else 0
            ),
            "total_subjects": (
                Subject.objects.filter(department=department).count()
                if department
                else 0
            ),
            "recent_announcements": (
                Announcement.objects.filter(
                    department=department, is_active=True
                ).count()
                if department
                else 0
            ),
        }

        return Response(data)