from django.db import models
from django.contrib.auth.models import AbstractUser

ROLE_CHOICES = [
    ("SUPERADMIN", "Super Admin"),
    ("ADMIN", "Admin"),
    ("FACULTY", "Faculty"),
    ("STUDENT", "Student"),
]


class User(AbstractUser):
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="STUDENT")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return f"{self.username} ({self.role})"


class UserCreationRequest(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    requested_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="creation_requests_made"
    )
    username = models.CharField(max_length=150)
    email = models.EmailField()
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="creation_requests_approved",
    )
    rejection_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.requested_by.username} requests {self.username} ({self.role}) - {self.status}"


class Dashboard(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="dashboards_created"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class DashboardCreationRequest(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    requested_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="dashboard_requests_made"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dashboard_requests_approved",
    )
    rejection_reason = models.TextField(blank=True, null=True)
    dashboard = models.OneToOneField(
        Dashboard,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="creation_request",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.requested_by.username} requests dashboard: {self.title} - {self.status}"


class PersonalDetail(models.Model):
    """
    Personal details for users (teachers, staff, students, etc.).
    Excludes SUPERADMIN where used in views/querysets.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="personal_detail"
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    designation = models.CharField(max_length=150, blank=True, null=True)
    department = models.CharField(max_length=150, blank=True, null=True)
    emergency_contact = models.CharField(max_length=50, blank=True, null=True)
    additional_info = models.JSONField(blank=True, null=True)

    # 👇 New field for storing image path or URL
    image_link = models.CharField(max_length=255, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"PersonalDetail: {self.user.username}"



class Attendance(models.Model):
    STATUS_CHOICES = [
        ("PRESENT", "Present"),
        ("ABSENT", "Absent"),
        ("ON_LEAVE", "On Leave"),
        ("HALF_DAY", "Half Day"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="attendances"
    )
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PRESENT")
    check_in = models.TimeField(blank=True, null=True)
    check_out = models.TimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_recorded"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.user.username} - {self.date} - {self.status}"