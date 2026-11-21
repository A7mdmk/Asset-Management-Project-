
from django import forms
from .models import AssetMaintenance
from .models import Asset, Category, Department
from .models import AssetAttachment

class AssetRegistrationForm(forms.Form):

    name = forms.CharField(
        max_length=120,
        label="Asset Name",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter asset name",
            }
        ),
    )

    description = forms.CharField(
        max_length=2000,
        required=False,
        label="Description",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Describe the asset...",
            }
        ),
    )

    asset_tag = forms.CharField(
        max_length=100,
        required=False,
        label="Asset Tag",
    )

    category = forms.ModelChoiceField(
        queryset=Category.objects.order_by("name"),
        empty_label="Select category",
        label="Category",
    )

    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(
            is_active=True
        ).order_by("name"),
        empty_label="Select department",
        label="Department",
    )

    location = forms.CharField(
        max_length=255,
        label="Location",
    )

    tracking_mode = forms.ChoiceField(
        choices=Asset.TrackingMode.choices,
        label="Tracking Mode",
    )

    quantity = forms.IntegerField(
        min_value=1,
        label="Quantity",
        widget=forms.NumberInput(
            attrs={"min": "1"}
        ),
    )

    condition = forms.ChoiceField(
        choices=Asset.Condition.choices,
        label="Condition",
    )

    def clean(self):
        cleaned_data = super().clean()

        tracking_mode = cleaned_data.get("tracking_mode")
        quantity = cleaned_data.get("quantity")

        if (
            tracking_mode == Asset.TrackingMode.INDIVIDUAL
            and quantity is not None
            and quantity != 1
        ):
            self.add_error(
                "quantity",
                "Individual assets must have quantity 1.",
            )

        return cleaned_data

class MaintenanceReportForm(forms.Form):
    title = forms.CharField(
        max_length=150,
        label="Issue Title",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Describe the issue briefly",
            }
        ),
    )

    description = forms.CharField(
        max_length=2000,
        label="Issue Description",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": (
                    "Explain the problem with the asset..."
                ),
            }
        ),
    )

    quantity = forms.IntegerField(
        min_value=1,
        label="Affected Quantity",
        initial=1,
        widget=forms.NumberInput(
            attrs={
                "min": "1",
            }
        ),
    )


class RepairCompletionForm(forms.Form):
    repair_notes = forms.CharField(
        max_length=2000,
        label="Repair Notes",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": (
                    "Describe the repair work completed..."
                ),
            }
        ),
    )

    return_to_service = forms.TypedChoiceField(
        label="Return Asset to Service?",
        choices=[
            ("true", "Yes - Return to available stock"),
            ("false", "No - Keep stock blocked"),
        ],
        coerce=lambda value: value == "true",
        empty_value=None,
        widget=forms.RadioSelect,
    )


class MaintenanceCancellationForm(forms.Form):
    reason = forms.CharField(
        max_length=2000,
        label="Cancellation Reason",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Explain why maintenance is cancelled..."
                ),
            }
        ),
    )

class InspectionRequestForm(forms.Form):
    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        label="Inspection Quantity",
        widget=forms.NumberInput(
            attrs={
                "min": "1",
                "placeholder": "Enter quantity",
            }
        ),
    )

from .models import AssetInspection


class InspectionCompletionForm(forms.Form):
    findings = forms.CharField(
        max_length=2000,
        label="Inspection Findings",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": (
                    "Describe the asset's condition "
                    "and your inspection findings..."
                ),
            }
        ),
    )

    recommendation = forms.ChoiceField(
        choices=AssetInspection.Recommendation.choices,
        label="Recommendation",
        widget=forms.Select,
    )

class DispositionRequestForm(forms.Form):
    reason = forms.CharField(
        max_length=2000,
        label="Disposition Reason",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": (
                    "Explain why this asset should "
                    "be retired, donated, recycled, "
                    "or disposed of..."
                ),
            }
        ),
    )

class DispositionExecutionForm(forms.Form):
    completion_notes = forms.CharField(
        max_length=2000,
        label="Completion Notes",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": (
                    "Describe how the disposition "
                    "was completed..."
                ),
            }
        ),
    )

class DispositionCancellationForm(forms.Form):
    reason = forms.CharField(
        max_length=1900,
        label="Cancellation Reason",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": (
                    "Explain why this disposition "
                    "should be cancelled..."
                ),
            }
        ),
    )

class AssetSpecificationForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        label="Specification Name",
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. RAM, Processor, Storage",
            }
        ),
    )

    value = forms.CharField(
        max_length=500,
        label="Specification Value",
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. 16 GB",
            }
        ),
    )

class AssetAttachmentUploadForm(forms.Form):
    title = forms.CharField(
        max_length=150,
        label="Attachment Title",
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. Laptop User Manual",
            }
        ),
    )

    attachment_type = forms.ChoiceField(
        choices=AssetAttachment.AttachmentType.choices,
        label="Attachment Type",
    )

    uploaded_file = forms.FileField(
        label="Attachment File",
        widget=forms.ClearableFileInput(
            attrs={
                "accept": ".pdf,.jpg,.jpeg,.png",
            }
        ),
    )

class AssetAttachmentEditForm(forms.Form):
    title = forms.CharField(
        max_length=150,
        label="Attachment Title",
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. Laptop User Manual",
            }
        ),
    )

    attachment_type = forms.ChoiceField(
        choices=AssetAttachment.AttachmentType.choices,
        label="Attachment Type",
    )
