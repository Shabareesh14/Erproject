from rest_framework import status, viewsets, generics
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
        if user.role == "SUPERADMIN":
            return User.objects.all()
        elif user.role == "ADMIN":
            return User.objects.filter(role__in=["FACULTY", "STUDENT"])
        elif user.role == "FACULTY":
            return User.objects.filter(role="STUDENT")
        else:
            return User.objects.filter(id=user.id)

    @action(detail=False, methods=["get"])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class UserCreationRequestViewSet(viewsets.ModelViewSet):
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

        # Check authentication
        if not user.is_authenticated:
            return Response(
                {"error": "Authentication credentials were not provided"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Check if user has role attribute
        if not hasattr(user, "role"):
            return Response(
                {"error": "User does not have a role assigned"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # STUDENT cannot create users
        if user.role == "STUDENT":
            return Response(
                {"error": "Students cannot create users"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # SUPERADMIN creates directly
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

        # FACULTY/ADMIN create request
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
        try:
            request_obj = self.get_object()
            user = request.user

            if request_obj.status != "PENDING":
                return Response(
                    {"error": f"Request already {request_obj.status.lower()}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate approver
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


class DashboardViewSet(viewsets.ModelViewSet):
    serializer_class = DashboardSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Dashboard.objects.filter(is_active=True)

    def get_permissions(self):
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
            return Response(
                {"error": "Only ADMIN/SUPERADMIN"}, status=status.HTTP_403_FORBIDDEN
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
        pending = DashboardCreationRequest.objects.filter(status="PENDING")
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)