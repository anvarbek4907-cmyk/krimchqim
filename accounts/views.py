from django.shortcuts import render

# Create your views here.


from django.contrib.auth import update_session_auth_hash
from django.db import transaction

from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .serializers import AuthResponseSerializer,ChangePasswordSerializer,LoginSerializer,ProfileSerializer,RegisterSerializer,UserSerializer


TAG = ["Autentifikatsiya"]


def auth_response(user, refresh):
    return {
        "user": UserSerializer(user).data,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


class RegisterView(generics.GenericAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=TAG,
        summary="Ro'yxatdan o'tish",
        responses={201: AuthResponseSerializer},
    )
    @transaction.atomic
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            auth_response(user, refresh),
            status=status.HTTP_201_CREATED,
        )


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=TAG,
        summary="Kirish va JWT token olish",
        responses={200: AuthResponseSerializer},
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)

        return Response(auth_response(user, refresh))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Chiqish va refresh tokenni bekor qilish",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "refresh": {"type": "string"}
                },
                "required": ["refresh"],
            }
        },
        responses={204: None},
    )
    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"refresh": "Refresh token yuborilishi shart."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {"refresh": "Refresh token noto'g'ri yoki bekor qilingan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "put", "patch", "head", "options"]

    def get_object(self):
        return self.request.user

    @extend_schema(tags=TAG, summary="Mening profilim")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(tags=TAG, summary="Profilni to'liq yangilash")
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(tags=TAG, summary="Profilni qisman yangilash")
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Parolni almashtirish",
        responses={200: AuthResponseSerializer},
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return Response(auth_response(user, refresh))