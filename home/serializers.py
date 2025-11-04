from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.db.models import Count, Avg
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


# ===================== EXISTING SERIALIZERS =====================


class UserSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "department",
            "department_name",
            "phone",
        ]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "role", "department"]

    def validate_role(self, value):
        return value.upper()

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            role=validated_data.get("role", "STUDENT"),
            department=validated_data.get("department"),
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
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = UserCreationRequest
        fields = [
            "id",
            "username",
            "email",
            "password",
            "role",
            "department",
            "department_name",
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


# ===================== NEW SERIALIZERS =====================


class DepartmentSerializer(serializers.ModelSerializer):
    hod_username = serializers.CharField(source="hod.username", read_only=True)
    hod_email = serializers.CharField(source="hod.email", read_only=True)
    total_faculty = serializers.SerializerMethodField()
    total_students = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "code",
            "description",
            "hod",
            "hod_username",
            "hod_email",
            "is_active",
            "total_faculty",
            "total_students",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_total_faculty(self, obj):
        return obj.members.filter(role="FACULTY").count()

    def get_total_students(self, obj):
        return obj.members.filter(role="STUDENT").count()


class SubjectSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    assigned_faculty_details = UserSerializer(
        source="assigned_faculty", many=True, read_only=True
    )

    class Meta:
        model = Subject
        fields = [
            "id",
            "name",
            "code",
            "department",
            "department_name",
            "semester",
            "credits",
            "assigned_faculty",
            "assigned_faculty_details",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AttendanceSerializer(serializers.ModelSerializer):
    student_username = serializers.CharField(source="student.username", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    marked_by_username = serializers.CharField(
        source="marked_by.username", read_only=True
    )

    class Meta:
        model = Attendance
        fields = [
            "id",
            "student",
            "student_username",
            "subject",
            "subject_name",
            "date",
            "status",
            "marked_by",
            "marked_by_username",
            "remarks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "marked_by", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["marked_by"] = self.context["request"].user
        return super().create(validated_data)


class MarksSerializer(serializers.ModelSerializer):
    student_username = serializers.CharField(source="student.username", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    faculty_username = serializers.CharField(source="faculty.username", read_only=True)
    percentage = serializers.ReadOnlyField()

    class Meta:
        model = Marks
        fields = [
            "id",
            "student",
            "student_username",
            "subject",
            "subject_name",
            "exam_type",
            "marks_obtained",
            "max_marks",
            "percentage",
            "faculty",
            "faculty_username",
            "remarks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "faculty", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["faculty"] = self.context["request"].user
        return super().create(validated_data)

    def validate(self, data):
        if data["marks_obtained"] > data["max_marks"]:
            raise serializers.ValidationError(
                "Marks obtained cannot exceed maximum marks"
            )
        return data


class LeaveRequestSerializer(serializers.ModelSerializer):
    student_username = serializers.CharField(source="student.username", read_only=True)
    approved_by_username = serializers.CharField(
        source="approved_by.username", read_only=True
    )
    total_days = serializers.ReadOnlyField()

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "student",
            "student_username",
            "start_date",
            "end_date",
            "reason",
            "status",
            "approved_by",
            "approved_by_username",
            "rejection_reason",
            "total_days",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "student",
            "status",
            "approved_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        validated_data["student"] = self.context["request"].user
        return super().create(validated_data)

    def validate(self, data):
        if data["end_date"] < data["start_date"]:
            raise serializers.ValidationError("End date cannot be before start date")
        return data


class ApproveLeaveRequestSerializer(serializers.Serializer):
    approve = serializers.BooleanField(required=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)


class AnnouncementSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "content",
            "created_by",
            "created_by_username",
            "target_audience",
            "department",
            "department_name",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class SystemSettingsSerializer(serializers.ModelSerializer):
    updated_by_username = serializers.CharField(
        source="updated_by.username", read_only=True
    )

    class Meta:
        model = SystemSettings
        fields = [
            "id",
            "academic_year",
            "current_semester",
            "min_attendance_percentage",
            "institution_name",
            "institution_email",
            "institution_phone",
            "updated_by",
            "updated_by_username",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_by", "updated_at"]

    def update(self, instance, validated_data):
        validated_data["updated_by"] = self.context["request"].user
        return super().update(instance, validated_data)


# ===================== REPORT SERIALIZERS =====================


class DepartmentSummarySerializer(serializers.Serializer):
    total_departments = serializers.IntegerField()
    active_departments = serializers.IntegerField()
    departments_with_hod = serializers.IntegerField()


class UserSummarySerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    superadmins = serializers.IntegerField()
    admins = serializers.IntegerField()
    faculty = serializers.IntegerField()
    students = serializers.IntegerField()


class DashboardOverviewSerializer(serializers.Serializer):
    departments = DepartmentSummarySerializer()
    users = UserSummarySerializer()
    pending_user_requests = serializers.IntegerField()
    pending_dashboard_requests = serializers.IntegerField()
    total_subjects = serializers.IntegerField()
    total_announcements = serializers.IntegerField()


class HODDashboardSerializer(serializers.Serializer):
    department_name = serializers.CharField()
    total_faculty = serializers.IntegerField()
    total_students = serializers.IntegerField()
    pending_leave_requests = serializers.IntegerField()
    total_subjects = serializers.IntegerField()
    recent_announcements = serializers.IntegerField()


class AttendanceSummarySerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    student_name = serializers.CharField()
    total_classes = serializers.IntegerField()
    present = serializers.IntegerField()
    absent = serializers.IntegerField()
    percentage = serializers.FloatField()