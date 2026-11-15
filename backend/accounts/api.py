from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import include, path
from rest_framework import generics, permissions, serializers

from .manager_permissions import is_manager

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, max_length=4096, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]
        extra_kwargs = {"email": {"required": True, "allow_blank": False}}

    def validate(self, attrs):
        user = User(username=attrs["username"], email=attrs["email"])
        try:
            validate_password(attrs["password"], user)
        except ValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return User.objects.create_user(**validated_data)
        except IntegrityError as error:
            username = User.normalize_username(validated_data["username"])
            if User.objects.filter(username=username).exists():
                raise serializers.ValidationError(
                    {"username": ["Пользователь с таким именем уже существует."]}
                ) from error
            raise


class MeSerializer(serializers.ModelSerializer):
    is_manager = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "is_manager"]
        read_only_fields = fields

    def get_is_manager(self, user) -> bool:
        return is_manager(user)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    authentication_classes = []
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveAPIView):
    serializer_class = MeSerializer

    def get_object(self):
        return self.request.user


urlpatterns = [
    path("auth/session/", include("accounts.session_api")),
    path("auth/register/", RegisterView.as_view(), name="api-register"),
    path("auth/me/", MeView.as_view(), name="api-me"),
]
