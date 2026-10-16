from decimal import Decimal

from django import forms

from apps.accounts.forms import BootstrapMixin
from apps.accounts.models import User
from apps.payments.models import WorkerPayment


class WorkerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.display_name} - {obj.get_specialty_display()}"


class PaymentForm(BootstrapMixin, forms.ModelForm):
    worker = WorkerChoiceField(queryset=User.objects.none())
    pay_now = forms.BooleanField(required=False, label="Already paid")
    method = forms.ChoiceField(
        choices=[("", "---------"), *WorkerPayment.Method.choices], required=False
    )
    reference = forms.CharField(max_length=100, required=False, label="Reference no.")

    class Meta:
        model = WorkerPayment
        fields = ["worker", "kind", "amount", "description"]
        labels = {"amount": "Amount (₹)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["worker"].queryset = User.objects.filter(
            role=User.Role.WORKER
        ).order_by("first_name", "last_name")
        self.fields["kind"].choices = [
            c for c in WorkerPayment.Kind.choices if c[0] != WorkerPayment.Kind.JOB
        ]
        self.fields["description"].required = True
        self._style_fields()

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount is None or amount == 0 or abs(amount) > Decimal("1000000"):
            raise forms.ValidationError("Enter an amount between ₹1 and ₹10,00,000.")
        if amount < 0 and self.data.get("kind") != WorkerPayment.Kind.ADJUSTMENT:
            raise forms.ValidationError("Only adjustments can be negative.")
        return amount

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("pay_now") and not cleaned.get("method"):
            self.add_error("method", "Choose how it was paid.")
        return cleaned


class PaymentEditForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = WorkerPayment
        fields = ["amount", "description"]
        labels = {"amount": "Amount (₹)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount is None or abs(amount) > Decimal("1000000"):
            raise forms.ValidationError("Enter an amount up to ₹10,00,000.")
        return amount


class MarkPaidForm(BootstrapMixin, forms.Form):
    method = forms.ChoiceField(choices=WorkerPayment.Method.choices)
    reference = forms.CharField(max_length=100, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
