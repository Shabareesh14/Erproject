from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from .models import User, UserCreationRequest, Dashboard, DashboardCreationRequest
from .models import PersonalDetail, Attendance


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "role"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "role"]

    def validate_role(self, value):
        return value.upper()

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            role=validated_data.get("role", "STUDENT"),
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data["email"], password=data["password"])
        if not user:
            raise serializers.ValidationError("Invalid email or password")
        return user


class UserCreationRequestSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(
        source="requested_by.username", read_only=True
    )
    approved_by_username = serializers.CharField(
        source="approved_by.username", read_only=True
    )

    class Meta:
        model = UserCreationRequest
        fields = [
            "id",
            "username",
            "email",
            "password",
            "role",
            "status",
            "requested_by",
            "requested_by_username",
            "approved_by",
            "approved_by_username",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "requested_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {"password": {"write_only": True}}

    def validate_role(self, value):
        return value.upper()

    def validate(self, data):
        request = self.context.get("request")
        if request and request.user:
            user_role = request.user.role
            requested_role = data.get("role", "").upper()

            if user_role == "FACULTY" and requested_role != "STUDENT":
                raise serializers.ValidationError(
                    {"role": "Faculty can only request to create STUDENT"}
                )

            if user_role == "ADMIN" and requested_role not in ["FACULTY", "STUDENT"]:
                raise serializers.ValidationError(
                    {"role": "Admin can only request FACULTY or STUDENT"}
                )

        return data

    def create(self, validated_data):
        validated_data["password"] = make_password(validated_data["password"])
        validated_data["requested_by"] = self.context["request"].user
        return super().create(validated_data)


class ApproveUserCreationSerializer(serializers.Serializer):
    approve = serializers.BooleanField(required=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)


class DashboardSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = Dashboard
        fields = [
            "id",
            "title",
            "description",
            "is_active",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class DashboardCreationRequestSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(
        source="requested_by.username", read_only=True
    )
    approved_by_username = serializers.CharField(
        source="approved_by.username", read_only=True
    )
    dashboard_data = DashboardSerializer(source="dashboard", read_only=True)

    class Meta:
        model = DashboardCreationRequest
        fields = [
            "id",
            "title",
            "description",
            "status",
            "requested_by",
            "requested_by_username",
            "approved_by",
            "approved_by_username",
            "rejection_reason",
            "dashboard",
            "dashboard_data",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "requested_by",
            "approved_by",
            "dashboard",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        validated_data["requested_by"] = self.context["request"].user

        if self.context["request"].user.role == "SUPERADMIN":
            request_obj = super().create(validated_data)
            request_obj.status = "APPROVED"
            request_obj.approved_by = self.context["request"].user

            dashboard = Dashboard.objects.create(
                title=request_obj.title,
                description=request_obj.description,
                created_by=self.context["request"].user,
            )
            request_obj.dashboard = dashboard
            request_obj.save()
            return request_obj

        return super().create(validated_data)


class ApproveDashboardCreationSerializer(serializers.Serializer):
    approve = serializers.BooleanField(required=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)


class PersonalDetailSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model = PersonalDetail
        fields = [
            "id",
            "user_id",
            "user_email",
            "phone",
            "address",
            "dob",
            "designation",
            "department",
            "emergency_contact",
            "additional_info",
            "image_link",  # 👈 Added
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "user_email", "user_id"]

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user if request else None

        if user and hasattr(user, "role") and user.role == "SUPERADMIN":
            raise serializers.ValidationError("Cannot create personal detail for SUPERADMIN.")
        return attrs


    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user if request else None

        if user and hasattr(user, "role") and user.role == "SUPERADMIN":
            raise serializers.ValidationError("Cannot create personal detail for SUPERADMIN.")
        return attrs



class AttendanceSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    recorded_by_email = serializers.EmailField(source="recorded_by.email", read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id",
            "user",
            "user_email",
            "date",
            "status",
            "check_in",
            "check_out",
            "notes",
            "recorded_by",
            "recorded_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "user_email", "recorded_by_email"]

    def validate(self, attrs):
        user = attrs.get("user") or (self.instance and self.instance.user)
        if user and user.role == "SUPERADMIN":
            raise serializers.ValidationError("Cannot record attendance for SUPERADMIN.")
        return attrs

    def create(self, validated_data):
        # set recorded_by to request.user if provided in context
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data.setdefault("recorded_by", request.user)
        return super().create(validated_data)