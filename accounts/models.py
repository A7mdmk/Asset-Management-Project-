
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from assets.models import Department


class DepartmentApprover(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="authorized_approvers",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="department_approvals",
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["department", "user"],
                name="unique_department_approver",
            )
        ]

    def clean(self):
        super().clean()

        errors = {}

        if self.user_id and not self.user.is_active:
            errors["user"] = "Approver must be an active user."

        if self.department_id and not self.department.is_active:
            errors["department"] = "Department must be active."

        if (
            self.user_id
            and not self.user.groups.filter(
                name="Approver/Admin"
            ).exists()
        ):
            errors["user"] = (
                "User must belong to the Approver/Admin group."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.user} - {self.department}"
