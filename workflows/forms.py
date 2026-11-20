
from django import forms
from .models import RequestApproval
from assets.models import Department


class ResourceRequestForm(forms.Form):
    destination_department = forms.ModelChoiceField(
        queryset=Department.objects.filter(
            is_active=True
        ).order_by("name"),
        empty_label="Select destination department",
        label="Destination Department",
    )

    quantity = forms.IntegerField(
        min_value=1,
        label="Quantity",
        widget=forms.NumberInput(
            attrs={
                "min": "1",
                "placeholder": "Enter quantity",
            }
        ),
    )

    reason = forms.CharField(
        max_length=2000,
        label="Reason for Request",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": (
                    "Explain why you need this resource..."
                ),
            }
        ),
    )

class ApprovalDecisionForm(forms.Form):

    decision = forms.ChoiceField(
        choices=RequestApproval.Decision.choices,
        widget=forms.RadioSelect,
        label="Decision",
    )

    comment = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Add a comment or explain "
                    "your rejection..."
                ),
            }
        ),
        label="Comment",
    )

    def clean(self):
        cleaned_data = super().clean()

        decision = cleaned_data.get("decision")
        comment = cleaned_data.get("comment", "").strip()

        if (
            decision == RequestApproval.Decision.REJECTED
            and not comment
        ):
            self.add_error(
                "comment",
                "A reason is required when rejecting a request.",
            )

        cleaned_data["comment"] = comment

        return cleaned_data
