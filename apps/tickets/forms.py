from django import forms

from apps.accounts.forms import BootstrapMixin, LocationChoiceField, location_queryset
from apps.tickets.models import Ticket

DATETIME_LOCAL = "%Y-%m-%dT%H:%M"


class TicketForm(BootstrapMixin, forms.ModelForm):
    location = LocationChoiceField(queryset=None, label="Building and room")

    class Meta:
        model = Ticket
        fields = [
            "title",
            "category",
            "location",
            "location_detail",
            "severity",
            "affected_people",
            "safety_flag",
            "description",
        ]
        labels = {
            "title": "What is the problem?",
            "location_detail": "Exact spot (optional)",
            "affected_people": "How many other people are affected?",
            "safety_flag": "This is a safety risk (sparks, gas smell, flooding, broken glass...)",
            "description": "Details",
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. Ceiling fan not working"}),
            "location_detail": forms.TextInput(attrs={"placeholder": "e.g. near the window"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["location"].queryset = location_queryset()
        self.fields["affected_people"].widget.attrs.update({"min": 0, "max": 500})
        self._style_fields()

    def clean_title(self):
        title = " ".join(self.cleaned_data["title"].split())
        if len(title) < 5:
            raise forms.ValidationError("Please describe the problem in at least 5 characters.")
        return title

    def clean_description(self):
        description = self.cleaned_data["description"].strip()
        if len(description) < 10:
            raise forms.ValidationError("Please add a few more details (at least 10 characters).")
        return description

    def clean_affected_people(self):
        value = self.cleaned_data["affected_people"] or 0
        if value > 500:
            raise forms.ValidationError("Enter a number between 0 and 500.")
        return value


class TicketReminderForm(BootstrapMixin, forms.Form):
    target = forms.ChoiceField(label="Send to")
    message = forms.CharField(
        max_length=400, required=False, widget=forms.TextInput(
            attrs={"placeholder": "Optional message, e.g. Please visit before 5 pm"}
        ),
    )
    remind_at = forms.DateTimeField(
        required=False,
        input_formats=[DATETIME_LOCAL],
        label="When (optional)",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DATETIME_LOCAL),
    )

    def __init__(self, *args, target_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target"].choices = list(target_choices)
        self._style_fields()


class PersonalReminderForm(BootstrapMixin, forms.Form):
    message = forms.CharField(
        max_length=400, widget=forms.TextInput(attrs={"placeholder": "What should we remind you?"})
    )
    remind_at = forms.DateTimeField(
        input_formats=[DATETIME_LOCAL],
        label="Remind me at",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DATETIME_LOCAL),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class CommentForm(BootstrapMixin, forms.Form):
    message = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Add an update or question..."}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
