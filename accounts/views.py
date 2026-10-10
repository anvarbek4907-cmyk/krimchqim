from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import AuthResponseSerializer,ChangePasswordSerializer,LoginSerializer,LogoutSerializer,ProfileSerializer,RegisterSerializer,TokenPairSerializer,issue_tokens,


TAG = ["Autentifikatsiya"]


class RegisterView(generics.GenericAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=TAG, summary="Ro'yxatdan o'tish", responses={201: AuthResponseSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = AuthResponseSerializer({"user": user, **issue_tokens(user)}).data
        return Response(data, status=status.HTTP_201_CREATED)


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=TAG, summary="Kirish (token olish)", responses={200: AuthResponseSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data
        data = AuthResponseSerializer(
            {"user": v["user"], "access": v["access"], "refresh": v["refresh"]}
        ).data
        return Response(data)


@extend_schema_view(
    post=extend_schema(
        tags=TAG,
        summary="Access tokenni yangilash",
        description="Refresh token orqali yangi access (va yangi refresh) oladi. Eski refresh bekor qilinadi.",
    )
)
class RefreshView(TokenRefreshView):
    pass


class LogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    @extend_schema(
        tags=TAG,
        summary="Chiqish (refresh tokenni bekor qilish)",
        responses={204: None},
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfileSerializer
    pagination_class = None

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
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    @extend_schema(tags=TAG, summary="Parolni almashtirish", responses={200: TokenPairSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save())
