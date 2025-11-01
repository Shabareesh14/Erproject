from rest_framework import status, viewsets, generics, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from .models import User, UserCreationRequest, Dashboard, DashboardCreationRequest
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    LoginSerializer,
    UserCreationRequestSerializer,
    ApproveUserCreationSerializer,
    DashboardSerializer,
    DashboardCreationRequestSerializer,
    ApproveDashboardCreationSerializer,
)
from .permissions import IsSuperAdmin, IsAdminOrSuperAdmin, IsFacultyOrAbove
from .models import PersonalDetail, Attendance
from .serializers import PersonalDetailSerializer, AttendanceSerializer


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


class RegisterView(generics.CreateAPIView):
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


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # SUPERADMIN sees all users
        if user.role == "SUPERADMIN":
            return User.objects.all()
        # ADMIN sees everyone except SUPERADMIN
        elif user.role == "ADMIN":
            return User.objects.exclude(role="SUPERADMIN")
        # FACULTY sees faculty and students (and staff) but not admins/superadmin
        elif user.role == "FACULTY":
            return User.objects.filter(role__in=["FACULTY", "STUDENT"])
        # STUDENT sees only themselves
        else:
            return User.objects.filter(id=user.id)

    @action(detail=False, methods=["get"])
    def me(self, request):
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)


class UserCreationRequestViewSet(viewsets.ModelViewSet):
    serializer_class = UserCreationRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # SUPERADMIN sees all requests
        if user.role == "SUPERADMIN":
            return UserCreationRequest.objects.all()
        # ADMIN sees requests except those created by SUPERADMIN (they approve subordinate requests)
        elif user.role == "ADMIN":
            return UserCreationRequest.objects.exclude(requested_by__role="SUPERADMIN")
        # FACULTY sees only their own requests
        elif user.role == "FACULTY":
            return UserCreationRequest.objects.filter(requested_by=user)
        return UserCreationRequest.objects.none()

    def create(self, request, *args, **kwargs):
        user = request.user

        # Check authentication
        if not user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        # Check if user has role attribute
        if not hasattr(user, "role"):
            return Response({"detail": "Invalid user."}, status=status.HTTP_400_BAD_REQUEST)

        # STUDENT cannot create users
        if user.role == "STUDENT":
            return Response({"detail": "Students cannot create user requests."}, status=status.HTTP_403_FORBIDDEN)

        # SUPERADMIN creates directly (bypass request)
        if user.role == "SUPERADMIN":
            data = request.data.copy()
            data["role"] = data.get("role", "STUDENT")
            serializer = RegisterSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            created_user = serializer.save()
            return Response(
                {"message": "User created directly by SUPERADMIN", "user": UserSerializer(created_user).data},
                status=status.HTTP_201_CREATED,
            )

        # FACULTY/ADMIN create request
        try:
            data = request.data.copy()
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            req = serializer.save(requested_by=user)
            return Response({"message": "User creation request submitted", "request": self.get_serializer(req).data},
                            status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        req = self.get_object()
        current = request.user

        # Only ADMIN or SUPERADMIN can approve/reject
        if current.role not in ["ADMIN", "SUPERADMIN"]:
            return Response({"detail": "Not authorized to approve requests."}, status=status.HTTP_403_FORBIDDEN)

        if req.status != "PENDING":
            return Response({"detail": "Request already processed."}, status=status.HTTP_400_BAD_REQUEST)

        approve_flag = request.data.get("approve", True)
        rejection_reason = request.data.get("rejection_reason", "")

        with transaction.atomic():
            if approve_flag:
                # prevent duplicate emails
                if User.objects.filter(email=req.email).exists():
                    return Response({"detail": "User with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)
                # req.password stored hashed by serializer; detect hashing to avoid double-hashing
                raw_password = req.password or ""
                is_hashed = raw_password.startswith("pbkdf2_") or raw_password.startswith("argon2") or raw_password.startswith("bcrypt_")
                if is_hashed:
                    # create user using hashed password directly
                    new_user = User.objects.create(
                        username=req.username,
                        email=req.email,
                        password=req.password,
                        role=req.role,
                    )
                else:
                    new_user = User.objects.create_user(
                        username=req.username,
                        email=req.email,
                        password=req.password,
                        role=req.role,
                    )
                req.status = "APPROVED"
                req.approved_by = current
                req.save()
                return Response({"message": "Request approved and user created", "user": UserSerializer(new_user).data},
                                status=status.HTTP_201_CREATED)
            else:
                req.status = "REJECTED"
                req.rejection_reason = rejection_reason
                req.approved_by = current
                req.save()
                return Response({"message": "Request rejected", "request": self.get_serializer(req).data},
                                status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def pending(self, request):
        user = request.user
        if user.role == "SUPERADMIN":
            qs = UserCreationRequest.objects.filter(status="PENDING")
        elif user.role == "ADMIN":
            qs = UserCreationRequest.objects.filter(status="PENDING").exclude(requested_by__role="SUPERADMIN")
        elif user.role == "FACULTY":
            qs = UserCreationRequest.objects.filter(requested_by=user, status="PENDING")
        else:
            qs = UserCreationRequest.objects.none()
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data, status=status.HTTP_200_OK)


class DashboardViewSet(viewsets.ModelViewSet):
    serializer_class = DashboardSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Dashboard.objects.filter(is_active=True)

    def get_permissions(self):
        # Only SUPERADMIN may mutate dashboards, others can read
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsSuperAdmin()]
        return [IsAuthenticated()]


class DashboardCreationRequestViewSet(viewsets.ModelViewSet):
    serializer_class = DashboardCreationRequestSerializer
    permission_classes = [IsAdminOrSuperAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == "SUPERADMIN":
            return DashboardCreationRequest.objects.all()
        return DashboardCreationRequest.objects.filter(requested_by=user)

    def create(self, request, *args, **kwargs):
        if request.user.role not in ["ADMIN", "SUPERADMIN"]:
            return Response({"detail": "Only ADMIN or SUPERADMIN can request dashboard creation."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        req_obj = serializer.save(requested_by=request.user)

        # If SUPERADMIN created the request, auto-approve and create the dashboard
        if request.user.role == "SUPERADMIN":
            with transaction.atomic():
                dash = Dashboard.objects.create(
                    title=req_obj.title,
                    description=req_obj.description,
                    created_by=request.user,
                    is_active=True,
                )
                req_obj.dashboard = dash
                req_obj.status = "APPROVED"
                req_obj.approved_by = request.user
                req_obj.save()
                return Response({"message": "Dashboard created by SUPERADMIN", "dashboard": DashboardSerializer(dash).data},
                                status=status.HTTP_201_CREATED)

        return Response(
            {
                "message": "Request submitted. Waiting for SUPERADMIN approval",
                "request": self.get_serializer(req_obj).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def approve(self, request, pk=None):
        req = self.get_object()
        if req.status != "PENDING":
            return Response({"detail": "Request already processed."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            dash = Dashboard.objects.create(
                title=req.title,
                description=req.description,
                created_by=request.user,
                is_active=True,
            )
            req.dashboard = dash
            req.status = "APPROVED"
            req.approved_by = request.user
            req.save()
            return Response({"message": "Dashboard created", "dashboard": DashboardSerializer(dash).data},
                            status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], permission_classes=[IsSuperAdmin])
    def pending(self, request):
        qs = DashboardCreationRequest.objects.filter(status="PENDING")
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data, status=status.HTTP_200_OK)


class ExcludeSuperadminMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        # If the model has a 'user' FK, exclude entries where the related user is SUPERADMIN
        try:
            if hasattr(qs.model, "user"):
                return qs.exclude(user__role="SUPERADMIN")
        except Exception:
            pass
        return qs


class PersonalDetailViewSet(ExcludeSuperadminMixin, viewsets.ModelViewSet):
    """
    Manage personal details for users other than SUPERADMIN.
    """

    queryset = PersonalDetail.objects.select_related("user").all()
    serializer_class = PersonalDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["user__username", "user__email", "designation", "department"]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_object(self):
        if self.kwargs.get("pk") == "me":
            obj, _ = PersonalDetail.objects.get_or_create(user=self.request.user)
            return obj
        return super().get_object()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        if request.user.role == "SUPERADMIN":
            return Response(
                {"detail": "SUPERADMIN cannot update personal details."},
                status=status.HTTP_403_FORBIDDEN,
            )

        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=instance.user)
        return Response(serializer.data)


class AttendanceViewSet(ExcludeSuperadminMixin, viewsets.ModelViewSet):
    """
    Attendance management.

    Rules:
    - Only FACULTY or ADMIN can create/update attendance.
    - STUDENTS can view only their own attendance.
    - FACULTY can view their own attendance + records they created.
    - ADMIN can view all (except SUPERADMIN, handled by mixin).
    """

    queryset = Attendance.objects.select_related("user", "recorded_by").all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["user__username", "user__email", "date", "status"]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()

        if user.role == "STUDENT":
            return qs.filter(user=user)

        if user.role == "FACULTY":
            # Faculty can view their own + records they recorded
            return qs.filter(Q(user=user) | Q(recorded_by=user))

        # Admin or Superadmin (filtered via mixin)
        return qs

    def create(self, request, *args, **kwargs):
        """Only FACULTY or ADMIN can create attendance."""
        if request.user.role not in ["FACULTY", "ADMIN"]:
            return Response(
                {"detail": "Only Faculty or Admin can create attendance."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Only FACULTY or ADMIN can update attendance."""
        if request.user.role not in ["FACULTY", "ADMIN"]:
            return Response(
                {"detail": "Only Faculty or Admin can update attendance."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            instance = self.get_object()
        except Attendance.DoesNotExist:
            return Response(
                {"detail": "Attendance record not found for the given ID."},
                status=status.HTTP_404_NOT_FOUND
            )

        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
    def perform_create(self, serializer):
        # record who created the attendance
        serializer.save(recorded_by=self.request.user)