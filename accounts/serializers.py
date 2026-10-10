from django.contrib.auth import authenticate,get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError 
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken



User  = get_user_model


def _run_password_validators(password, user =None):
    try:
        validate_password(password, user=user)
    except ValidationError as exc :
        raise serializers.ValidationError(list(exc.messages))

class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username =serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
class AuthResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    access =serializers.CharField()
    refresh =serializers.CharField()

def build_auth_payload(user):
    refresh = RefreshToken.for_user(user)
    return {
        "user": UserSerializer(user).data,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }

class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password2 = serializers.CharField(write_only=True, style={"input_type": "password"})
    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Bu username band.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Parollar mos kelmadi."})
        probe = User(username=attrs["username"], email=attrs.get("email", ""))
        _run_password_validators(attrs["password"], user=probe)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("password2")
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)

    def to_representation(self, instance):
        return build_auth_payload(instance)
    

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["username"],
            password=attrs["password"],
        )
        if user is None or not user.is_active:
            raise serializers.ValidationError("Username yoki parol noto'g'ri.")
        return build_auth_payload(user)


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, attrs):
        try:
            old = RefreshToken(attrs["refresh"])
        except TokenError:
            raise serializers.ValidationError(
                {"refresh": "Refresh token noto'g'ri yoki bekor qilingan."}
            )

        try:
            user = User.objects.get(pk=old["user_id"], is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError({"refresh": "Foydalanuvchi topilmadi."})

        old.blacklist()
        return build_auth_payload(user)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate_refresh(self, value):
        try:
            token = RefreshToken(value)
        except TokenError:
            raise serializers.ValidationError("Refresh token noto'g'ri yoki bekor qilingan.")

        user = self.context["request"].user
        if str(token.get("user_id")) != str(user.pk):
            raise serializers.ValidationError("Bu token sizga tegishli emas.")

        self._token = token
        return value

    def save(self, **kwargs):
        self._token.blacklist()


class ProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Eski parol noto'g'ri.")
        return value

    def validate_new_password(self, value):
        _run_password_validators(value, user=self.context["request"].user)
        return value

    @transaction.atomic
    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])

        for outstanding in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=outstanding)

        return build_auth_payload(user)