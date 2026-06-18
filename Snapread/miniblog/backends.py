from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailBackend(ModelBackend):
   
    def authenticate(self, request, email=None, password=None, **kwargs):
        if not email or not password:
            return None
        try:
            # case-insensitive email match
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None