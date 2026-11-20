
from django import forms

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
