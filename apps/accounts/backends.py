from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    """Authenticate with either the account email address or the username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)
        if not username or password is None:
            return None

        user_model = get_user_model()
        identifier = username.strip()
        user = user_model.objects.filter(username__iexact=identifier).first()
        if user is None and "@" in identifier:
            user = user_model.objects.filter(email__iexact=identifier).order_by("id").first()
        if user is None:
            # Run the hasher anyway so timing does not reveal unknown accounts
            user_model().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
