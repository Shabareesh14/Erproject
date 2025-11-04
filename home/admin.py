from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
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


class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ("username", "email", "role", "department", "is_staff", "is_active")
    list_filter = ("role", "department", "is_staff", "is_active")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "username",
                    "email",
                    "password",
                    "role",
                    "department",
                    "phone",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_staff",
                    "is_active",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "role",
                    "department",
                    "phone",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )
    search_fields = ("email", "username")
    ordering = ("email",)


admin.site.register(User, CustomUserAdmin)


@admin.register(UserCreationRequest)
class UserCreationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "email",
        "role",
        "department",
        "requested_by",
        "status",
        "created_at",
    )
    list_filter = ("status", "role", "department", "created_at")
    search_fields = ("username", "email", "requested_by__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ("title", "created_by", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("title", "description", "created_by__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(DashboardCreationRequest)
class DashboardCreationRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "requested_by", "status", "dashboard", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "requested_by__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "hod", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "code", "hod__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "department", "semester", "credits", "is_active")
    list_filter = ("department", "semester", "is_active")
    search_fields = ("name", "code")
    filter_horizontal = ("assigned_faculty",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "subject", "date", "status", "marked_by", "created_at")
    list_filter = ("status", "date", "subject", "marked_by")
    search_fields = ("student__username", "subject__name")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "date"


@admin.register(Marks)
class MarksAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "subject",
        "exam_type",
        "marks_obtained",
        "max_marks",
        "percentage",
        "faculty",
    )
    list_filter = ("exam_type", "subject", "faculty")
    search_fields = ("student__username", "subject__name")
    readonly_fields = ("created_at", "updated_at", "percentage")


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "start_date",
        "end_date",
        "total_days",
        "status",
        "approved_by",
        "created_at",
    )
    list_filter = ("status", "start_date", "approved_by")
    search_fields = ("student__username", "reason")
    readonly_fields = ("created_at", "updated_at", "total_days")
    date_hierarchy = "start_date"


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "created_by",
        "target_audience",
        "department",
        "is_active",
        "created_at",
    )
    list_filter = ("target_audience", "department", "is_active", "created_at")
    search_fields = ("title", "content", "created_by__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "academic_year",
        "current_semester",
        "min_attendance_percentage",
        "updated_by",
        "updated_at",
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # Only allow one instance
        return not SystemSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion
        return False