from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, Transaction, Wallet
from .permissions import IsActiveUser, IsOwner
from .serializers import CategorySerializer,SummaryQuerySerializer,SummaryResponseSerializer,TransactionFilterSerializer,TransactionSerializer,WalletSerializer



def _is_schema_generation(view):
    return getattr(view, "swagger_fake_view", False)


@extend_schema_view(
    get=extend_schema(
        tags=["Kategoriyalar"],
        summary="Kategoriyalar ro'yxati",
        parameters=[
            OpenApiParameter("type", str, enum=["income", "expense"], description="Tur bo'yicha filtr")
        ],
    ),
    post=extend_schema(tags=["Kategoriyalar"], summary="Kategoriya yaratish"),
)
class CategoryListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsActiveUser]
    serializer_class = CategorySerializer

    def get_queryset(self):
        if _is_schema_generation(self):
            return Category.objects.none()
        qs = Category.objects.filter(user=self.request.user)
        type_ = self.request.query_params.get("type")
        if type_ in Category.Type.values:
            qs = qs.filter(type=type_)
        return qs


@extend_schema_view(
    get=extend_schema(tags=["Kategoriyalar"], summary="Kategoriyani ko'rish"),
    put=extend_schema(tags=["Kategoriyalar"], summary="Kategoriyani to'liq yangilash"),
    patch=extend_schema(tags=["Kategoriyalar"], summary="Kategoriyani qisman yangilash"),
    delete=extend_schema(
        tags=["Kategoriyalar"],
        summary="Kategoriyani o'chirish",
        description="Tranzaksiyasi bor kategoriyani o'chirib bo'lmaydi (400).",
    ),
)
class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsActiveUser, IsOwner]
    serializer_class = CategorySerializer

    def get_queryset(self):
        if _is_schema_generation(self):
            return Category.objects.none()
        return Category.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        CategorySerializer.ensure_deletable(instance)
        instance.delete()


@extend_schema_view(
    get=extend_schema(tags=["Hamyonlar"], summary="Hamyonlar ro'yxati"),
    post=extend_schema(tags=["Hamyonlar"], summary="Hamyon yaratish"),
)
class WalletListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsActiveUser]
    serializer_class = WalletSerializer

    def get_queryset(self):
        if _is_schema_generation(self):
            return Wallet.objects.none()
        return Wallet.objects.filter(user=self.request.user)


@extend_schema_view(
    get=extend_schema(tags=["Hamyonlar"], summary="Hamyonni ko'rish"),
    put=extend_schema(tags=["Hamyonlar"], summary="Hamyonni to'liq yangilash"),
    patch=extend_schema(tags=["Hamyonlar"], summary="Hamyonni qisman yangilash"),
    delete=extend_schema(
        tags=["Hamyonlar"],
        summary="Hamyonni o'chirish",
        description="Hamyon bilan birga uning tranzaksiyalari ham o'chadi.",
    ),
)
class WalletDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsActiveUser, IsOwner]
    serializer_class = WalletSerializer

    def get_queryset(self):
        if _is_schema_generation(self):
            return Wallet.objects.none()
        return Wallet.objects.filter(user=self.request.user)


@extend_schema_view(
    get=extend_schema(
        tags=["Tranzaksiyalar"],
        summary="Kirim-chiqimlar ro'yxati (filtr, qidiruv, tartiblash)",
        parameters=[TransactionFilterSerializer],
    ),
    post=extend_schema(
        tags=["Tranzaksiyalar"],
        summary="Kirim yoki chiqim qo'shish",
        description=(
            "Turi (kirim/chiqim) tanlangan **kategoriya** turidan olinadi. "
            "Hamyon balansi avtomatik o'zgaradi; chiqim balansdan oshsa 400 qaytadi."
        ),
    ),
)
class TransactionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsActiveUser]
    serializer_class = TransactionSerializer

    def get_queryset(self):
        if _is_schema_generation(self):
            return Transaction.objects.none()
        qs = Transaction.objects.filter(user=self.request.user).select_related(
            "wallet", "category"
        )
        filters = TransactionFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return filters.filter_queryset(qs)


@extend_schema_view(
    get=extend_schema(tags=["Tranzaksiyalar"], summary="Tranzaksiyani ko'rish"),
    put=extend_schema(tags=["Tranzaksiyalar"], summary="Tranzaksiyani to'liq yangilash"),
    patch=extend_schema(tags=["Tranzaksiyalar"], summary="Tranzaksiyani qisman yangilash"),
    delete=extend_schema(
        tags=["Tranzaksiyalar"],
        summary="Tranzaksiyani o'chirish",
        description="Hamyon balansi avtomatik qaytariladi.",
    ),
)
class TransactionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsActiveUser, IsOwner]
    serializer_class = TransactionSerializer

    def get_queryset(self):
        if _is_schema_generation(self):
            return Transaction.objects.none()
        return Transaction.objects.filter(user=self.request.user).select_related(
            "wallet", "category"
        )

    def perform_destroy(self, instance):
        TransactionSerializer.delete_instance(instance)


class SummaryView(APIView):
    permission_classes = [IsActiveUser]
    pagination_class = None

    @extend_schema(
        tags=["Statistika"],
        summary="Jami kirim, chiqim va kategoriyalar kesimi",
        parameters=[SummaryQuerySerializer],
        responses=SummaryResponseSerializer,
    )
    def get(self, request):
        query = SummaryQuerySerializer(data=request.query_params, context={"request": request})
        query.is_valid(raise_exception=True)
        data = query.build(request.user)
        return Response(SummaryResponseSerializer(data).data)
