import secrets
import string

from django import forms
from django.contrib.auth import password_validation
from django.db.models import Q

from apps.accounts import features as F
from apps.accounts.models import User
from apps.locations.models import Building, Location


def generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length - 2))
        candidate += secrets.choice("!@#$%&*") + secrets.choice(string.digits)
        if any(c.islower() for c in candidate) and any(c.isupper() for c in candidate):
            return candidate


class LocationChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.full_name


def location_queryset():
    return Location.objects.select_related("building").order_by("building__name", "floor", "name")


def _email_taken(email, exclude_pk=None) -> bool:
    qs = User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email))
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


class BootstrapMixin:
    """Adds Bootstrap classes to every widget."""

    def _style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxSelectMultiple):
                continue
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class SignupForm(BootstrapMixin, forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(help_text="You will sign in with this email address.")
    phone = forms.CharField(max_length=20, required=False)
    department = forms.CharField(
        max_length=120, required=False, label="Course / hostel room",
        help_text="For example: B.Tech CSE, Hostel A room 214",
    )
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput, strip=False)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput, strip=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if _email_taken(email):
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The two passwords do not match.")
        if p1:
            probe = User(
                username=cleaned.get("email", ""),
                email=cleaned.get("email", ""),
                first_name=cleaned.get("first_name", ""),
            )
            try:
                password_validation.validate_password(p1, probe)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self) -> User:
        data = self.cleaned_data
        user = User(
            username=data["email"],
            email=data["email"],
            first_name=data["first_name"].strip(),
            last_name=data.get("last_name", "").strip(),
            phone=data.get("phone", "").strip(),
            department=data.get("department", "").strip(),
            role=User.Role.STUDENT,
        )
        user.apply_role_defaults()
        user.set_password(data["password1"])
        user.save()
        return user


class PortalUserForm(BootstrapMixin, forms.ModelForm):
    """Admin portal form to create or edit any account, including its feature access."""

    features = forms.MultipleChoiceField(
        choices=[(code, label) for code, label, _ in F.FEATURES],
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Admins always have every feature.",
    )
    password = forms.CharField(
        required=False,
        strip=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text="Leave empty to generate a secure password automatically.",
    )
    area = forms.ModelChoiceField(
        queryset=Building.objects.order_by("name"), required=False, label="Home area / building"
    )
    current_location = LocationChoiceField(queryset=Location.objects.none(), required=False)

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "role",
            "phone",
            "department",
            "is_active",
            "specialty",
            "area",
            "current_location",
            "rate_per_job",
            "availability",
        ]
        labels = {
            "is_active": "Account active (can sign in)",
            "rate_per_job": "Pay per verified job (₹)",
            "department": "Department / course / room",
        }

    def __init__(self, *args, editing_self=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.editing_self = editing_self
        self.fields["email"].required = True
        self.fields["first_name"].required = True
        self.fields["current_location"].queryset = location_queryset()
        if self.instance.pk:
            del self.fields["password"]
            self.initial["features"] = list(self.instance.features or [])
        else:
            role = self.data.get("role") or self.initial.get("role") or User.Role.STUDENT
            self.initial.setdefault("features", F.default_features_for_role(role))
        self._style_fields()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if _email_taken(email, exclude_pk=self.instance.pk):
            raise forms.ValidationError("Another account already uses this email.")
        return email

    def clean(self):
        cleaned = super().clean()
        if self.editing_self:
            if cleaned.get("role") != User.Role.ADMIN:
                self.add_error("role", "You cannot remove your own admin role.")
            if not cleaned.get("is_active"):
                self.add_error("is_active", "You cannot deactivate your own account.")
        password = cleaned.get("password")
        if password:
            try:
                password_validation.validate_password(password)
            except forms.ValidationError as exc:
                self.add_error("password", exc)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        old_email = None
        if user.pk:
            old_email = User.objects.filter(pk=user.pk).values_list("email", flat=True).first()
        if not user.pk or (old_email and user.username.lower() == old_email.lower()):
            user.username = user.email
        user.features = F.clean_feature_codes(self.cleaned_data.get("features"))
        is_admin = user.role == User.Role.ADMIN
        user.is_staff = is_admin
        user.is_superuser = is_admin
        if is_admin:
            user.features = list(F.ALL_FEATURE_CODES)

        self.generated_password = None
        if "password" in self.fields:
            raw = self.cleaned_data.get("password") or ""
            if not raw:
                raw = generate_password()
                self.generated_password = raw
            user.set_password(raw)
        if commit:
            user.save()
        return user


class ProfileForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "department"]
        labels = {"department": "Department / course / room"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class WorkerLocationForm(BootstrapMixin, forms.Form):
    current_location = LocationChoiceField(
        queryset=Location.objects.none(), required=False, label="I am at"
    )
    availability = forms.ChoiceField(choices=User.Availability.choices)
    lat = forms.DecimalField(
        required=False, max_digits=9, decimal_places=6, min_value=-90, max_value=90,
        widget=forms.HiddenInput,
    )
    lng = forms.DecimalField(
        required=False, max_digits=9, decimal_places=6, min_value=-180, max_value=180,
        widget=forms.HiddenInput,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["current_location"].queryset = location_queryset()
        self._style_fields()

    def clean(self):
        cleaned = super().clean()
        if (cleaned.get("lat") is None) != (cleaned.get("lng") is None):
            raise forms.ValidationError("GPS position is incomplete. Please try again.")
        return cleaned


class BuildingForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Building
        fields = ["name", "code", "is_critical", "description"]
        labels = {"is_critical": "Critical building (health centre, mess, labs...)"}
        widgets = {"description": forms.TextInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].required = False
        self._style_fields()


class LocationForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Location
        fields = ["building", "name", "floor", "is_critical", "is_common_area"]
        labels = {"name": "Room / area", "is_common_area": "Common area"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["building"].queryset = Building.objects.order_by("name")
        self._style_fields()

    def clean(self):
        cleaned = super().clean()
        building, name = cleaned.get("building"), (cleaned.get("name") or "").strip()
        if building and name and Location.objects.filter(
            building=building, name__iexact=name
        ).exclude(pk=self.instance.pk).exists():
            self.add_error("name", "This room already exists in that building.")
        return cleaned
