from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator

ROLE_CHOICES = [
    ("SUPERADMIN", "Super Admin"),
    ("ADMIN", "Admin"),
    ("FACULTY", "Faculty"),
    ("STUDENT", "Student"),
]


class Department(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    hod = models.OneToOneField(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_headed",
        limit_choices_to={"role": "ADMIN"},
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class User(AbstractUser):
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="STUDENT")
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )
    phone = models.CharField(max_length=15, blank=True)

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
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True
    )
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


class Subject(models.Model):
    SEMESTER_CHOICES = [(i, f"Semester {i}") for i in range(1, 9)]

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="subjects"
    )
    semester = models.IntegerField(choices=SEMESTER_CHOICES)
    credits = models.IntegerField(default=3)
    assigned_faculty = models.ManyToManyField(
        User,
        related_name="subjects_teaching",
        limit_choices_to={"role": "FACULTY"},
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["department", "semester", "name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Attendance(models.Model):
    STATUS_CHOICES = [
        ("PRESENT", "Present"),
        ("ABSENT", "Absent"),
        ("LATE", "Late"),
    ]

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="attendances",
        limit_choices_to={"role": "STUDENT"},
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="attendances"
    )
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    marked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="attendances_marked"
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        unique_together = ["student", "subject", "date"]

    def __str__(self):
        return f"{self.student.username} - {self.subject.code} - {self.date} - {self.status}"


class Marks(models.Model):
    EXAM_TYPE_CHOICES = [
        ("INTERNAL_1", "Internal Exam 1"),
        ("INTERNAL_2", "Internal Exam 2"),
        ("INTERNAL_3", "Internal Exam 3"),
        ("ASSIGNMENT", "Assignment"),
        ("QUIZ", "Quiz"),
        ("FINAL", "Final Exam"),
    ]

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="marks",
        limit_choices_to={"role": "STUDENT"},
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="marks")
    exam_type = models.CharField(max_length=20, choices=EXAM_TYPE_CHOICES)
    marks_obtained = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0)]
    )
    max_marks = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0)]
    )
    faculty = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="marks_entered"
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["student", "subject", "exam_type"]

    def __str__(self):
        return f"{self.student.username} - {self.subject.code} - {self.exam_type}"

    @property
    def percentage(self):
        if self.max_marks > 0:
            return (self.marks_obtained / self.max_marks) * 100
        return 0


class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="leave_requests",
        limit_choices_to={"role": "STUDENT"},
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leave_requests_approved",
    )
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student.username} - {self.start_date} to {self.end_date} - {self.status}"

    @property
    def total_days(self):
        return (self.end_date - self.start_date).days + 1


class Announcement(models.Model):
    TARGET_AUDIENCE_CHOICES = [
        ("ALL", "All Users"),
        ("STUDENT", "Students"),
        ("FACULTY", "Faculty"),
        ("ADMIN", "Admins"),
        ("DEPARTMENT", "Department Specific"),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="announcements_created"
    )
    target_audience = models.CharField(max_length=20, choices=TARGET_AUDIENCE_CHOICES)
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="announcements",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.target_audience}"


class SystemSettings(models.Model):
    academic_year = models.CharField(max_length=20, default="2024-2025")
    current_semester = models.IntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(8)]
    )
    min_attendance_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=75.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    institution_name = models.CharField(
        max_length=200, default="Educational Institution"
    )
    institution_email = models.EmailField(blank=True)
    institution_phone = models.CharField(max_length=15, blank=True)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="settings_updated"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"

    def __str__(self):
        return f"Settings - {self.academic_year}"

    @classmethod
    def get_settings(cls):
        settings, created = cls.objects.get_or_create(pk=1)
        return settings