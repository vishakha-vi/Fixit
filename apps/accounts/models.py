from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        REQUESTER = "requester", "Requester"
        TECHNICIAN = "technician", "Technician"
        ADMIN = "admin", "Admin"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.REQUESTER,
        help_text="Role determining permissions and access rights in FixIt",
    )

    def is_requester(self) -> bool:
        return self.role == self.Role.REQUESTER

    def is_technician(self) -> bool:
        return self.role == self.Role.TECHNICIAN

    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"
