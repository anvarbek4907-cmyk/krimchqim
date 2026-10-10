
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import serializers

from .models import Category, Transaction, Wallet

ZERO = Decimal("0.00")

class UserOwnedPrimaryKeyField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        queryset = super().get_queryset()
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return queryset.none()
        return queryset.filter(user=request.user)

class CategorySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=100)
    type = serializers.ChoiceField(choices=Category.Type.choices)
    created_at = serializers.DateTimeField(read_only=True)

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Nom bo'sh bo'lmasligi kerak.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        name = attrs.get("name", self.instance.name if self.instance else None)
        type_ = attrs.get("type", self.instance.type if self.instance else None)

        duplicates = Category.objects.filter(user=user, name__iexact=name, type=type_)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                {"name": "Bunday nomli kategoriya shu turda allaqachon mavjud."}
            )

        if (
            self.instance
            and type_ != self.instance.type
            and self.instance.transactions.exists()
        ):
            raise serializers.ValidationError(
                {"type": "Tranzaksiyasi bor kategoriyaning turini o'zgartirib bo'lmaydi."}
            )
        return attrs

    def create(self, validated_data):
        return Category.objects.create(user=self.context["request"].user, **validated_data)

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance

    @staticmethod
    def ensure_deletable(instance):
        if instance.transactions.exists():
            raise serializers.ValidationError(
                {"detail": "Bu kategoriyada tranzaksiyalar bor, avval ularni o'chiring."}
            )


class WalletSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=100)
    currency = serializers.ChoiceField(choices=Wallet.Currency.choices, required=False)
    balance = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=ZERO,
        required=False,
        help_text="Boshlang'ich balans (faqat yaratishda). Keyin balans tranzaksiyalar orqali o'zgaradi.",
    )
    created_at = serializers.DateTimeField(read_only=True)

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Nom bo'sh bo'lmasligi kerak.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user

        if self.instance and "balance" in attrs:
            raise serializers.ValidationError(
                {"balance": "Balansni to'g'ridan-to'g'ri o'zgartirib bo'lmaydi, tranzaksiya qo'shing."}
            )

        if "name" in attrs:
            duplicates = Wallet.objects.filter(user=user, name__iexact=attrs["name"])
            if self.instance:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError(
                    {"name": "Bunday nomli hamyon allaqachon mavjud."}
                )

        if (
            self.instance
            and "currency" in attrs
            and attrs["currency"] != self.instance.currency
            and self.instance.transactions.exists()
        ):
            raise serializers.ValidationError(
                {"currency": "Tranzaksiyasi bor hamyonning valyutasini o'zgartirib bo'lmaydi."}
            )
        return attrs

    def create(self, validated_data):
        return Wallet.objects.create(
            user=self.context["request"].user,
            name=validated_data["name"],
            currency=validated_data.get("currency", Wallet.Currency.UZS),
            balance=validated_data.get("balance", ZERO),
        )

    def update(self, instance, validated_data):
        for field in ("name", "currency"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.save()
        return instance



class TransactionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    wallet = UserOwnedPrimaryKeyField(queryset=Wallet.objects.all())
    category = UserOwnedPrimaryKeyField(queryset=Category.objects.all())
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)
    date = serializers.DateField(required=False, help_text="Berilmasa bugungi sana olinadi.")

    # faqat o'qish uchun
    type = serializers.CharField(source="category.type", read_only=True)
    wallet_name = serializers.CharField(source="wallet.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    def validate_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("Kelajak sanasini kiritib bo'lmaydi.")
        return value

    @staticmethod
    def _delta(category, amount):
        return amount if category.type == Category.Type.INCOME else -amount

    @staticmethod
    def _lock_wallet(pk):
        return Wallet.objects.select_for_update().get(pk=pk)

    @transaction.atomic
    def create(self, validated_data):
        category = validated_data["category"]
        amount = validated_data["amount"]
        wallet = self._lock_wallet(validated_data["wallet"].pk)

        wallet.balance += self._delta(category, amount)
        if wallet.balance < 0:
            raise serializers.ValidationError({"amount": "Hamyonda mablag' yetarli emas."})
        wallet.save(update_fields=["balance"])

        return Transaction.objects.create(
            user=self.context["request"].user,
            wallet=wallet,
            category=category,
            amount=amount,
            description=validated_data.get("description", ""),
            date=validated_data.get("date") or timezone.localdate(),
        )

    @transaction.atomic
    def update(self, instance, validated_data):
        old_wallet = self._lock_wallet(instance.wallet_id)
        target_pk = validated_data["wallet"].pk if "wallet" in validated_data else instance.wallet_id
        new_wallet = old_wallet if target_pk == old_wallet.pk else self._lock_wallet(target_pk)

        category = validated_data.get("category", instance.category)
        amount = validated_data.get("amount", instance.amount)

        # eski ta'sirni qaytaramiz, yangisini qo'llaymiz
        old_wallet.balance -= instance.signed_amount
        new_wallet.balance += self._delta(category, amount)

        if old_wallet.balance < 0 or new_wallet.balance < 0:
            raise serializers.ValidationError(
                {"amount": "O'zgartirishdan so'ng hamyon balansi manfiy bo'lib qoladi."}
            )

        old_wallet.save(update_fields=["balance"])
        if new_wallet is not old_wallet:
            new_wallet.save(update_fields=["balance"])

        instance.wallet = new_wallet
        instance.category = category
        instance.amount = amount
        if "description" in validated_data:
            instance.description = validated_data["description"]
        if "date" in validated_data:
            instance.date = validated_data["date"]
        instance.save()
        return instance

    @staticmethod
    @transaction.atomic
    def delete_instance(instance):
        """O'chirishda hamyon balansi ham qaytariladi."""
        wallet = Wallet.objects.select_for_update().get(pk=instance.wallet_id)
        wallet.balance -= instance.signed_amount
        if wallet.balance < 0:
            raise serializers.ValidationError(
                {"detail": "Bu kirimni o'chirsangiz hamyon balansi manfiy bo'lib qoladi."}
            )
        wallet.save(update_fields=["balance"])
        instance.delete()


 
class TransactionFilterSerializer(serializers.Serializer):
    ORDERING_CHOICES = ["date", "-date", "amount", "-amount", "created_at", "-created_at"]

    type = serializers.ChoiceField(choices=Category.Type.choices, required=False)
    category = serializers.IntegerField(required=False)
    wallet = serializers.IntegerField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    min_amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    max_amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    search = serializers.CharField(required=False, help_text="Izoh bo'yicha qidirish")
    ordering = serializers.ChoiceField(choices=ORDERING_CHOICES, required=False)

    def validate(self, attrs):
        if "date_from" in attrs and "date_to" in attrs and attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError({"date_from": "date_from date_to dan katta bo'lmasligi kerak."})
        if "min_amount" in attrs and "max_amount" in attrs and attrs["min_amount"] > attrs["max_amount"]:
            raise serializers.ValidationError({"min_amount": "min_amount max_amount dan katta bo'lmasligi kerak."})
        return attrs

    def filter_queryset(self, queryset):
        d = self.validated_data
        if "type" in d:
            queryset = queryset.filter(category__type=d["type"])
        if "category" in d:
            queryset = queryset.filter(category_id=d["category"])
        if "wallet" in d:
            queryset = queryset.filter(wallet_id=d["wallet"])
        if "date_from" in d:
            queryset = queryset.filter(date__gte=d["date_from"])
        if "date_to" in d:
            queryset = queryset.filter(date__lte=d["date_to"])
        if "min_amount" in d:
            queryset = queryset.filter(amount__gte=d["min_amount"])
        if "max_amount" in d:
            queryset = queryset.filter(amount__lte=d["max_amount"])
        if d.get("search"):
            queryset = queryset.filter(description__icontains=d["search"])
        if "ordering" in d:
            queryset = queryset.order_by(d["ordering"], "-id")
        return queryset


class SummaryQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    wallet = UserOwnedPrimaryKeyField(queryset=Wallet.objects.all(), required=False)

    def validate(self, attrs):
        if "date_from" in attrs and "date_to" in attrs and attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError({"date_from": "date_from date_to dan katta bo'lmasligi kerak."})
        return attrs

    def build(self, user):
        d = self.validated_data
        qs = Transaction.objects.filter(user=user)
        if "wallet" in d:
            qs = qs.filter(wallet=d["wallet"])
        if "date_from" in d:
            qs = qs.filter(date__gte=d["date_from"])
        if "date_to" in d:
            qs = qs.filter(date__lte=d["date_to"])

        totals = qs.aggregate(
            total_income=Sum("amount", filter=Q(category__type=Category.Type.INCOME)),
            total_expense=Sum("amount", filter=Q(category__type=Category.Type.EXPENSE)),
            transactions_count=Count("id"),
        )
        income = totals["total_income"] or ZERO
        expense = totals["total_expense"] or ZERO

        rows = (
            qs.values("category_id", "category__name", "category__type")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("category__type", "-total")
        )
        categories = [
            {
                "category": r["category_id"],
                "name": r["category__name"],
                "type": r["category__type"],
                "total": r["total"],
                "count": r["count"],
            }
            for r in rows
        ]
        return {
            "total_income": income,
            "total_expense": expense,
            "balance": income - expense,
            "transactions_count": totals["transactions_count"],
            "categories": categories,
        }


class CategoryTotalSerializer(serializers.Serializer):
    category = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.ChoiceField(choices=Category.Type.choices)
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    count = serializers.IntegerField()


class SummaryResponseSerializer(serializers.Serializer):
    total_income = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_expense = serializers.DecimalField(max_digits=14, decimal_places=2)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    transactions_count = serializers.IntegerField()
    categories = CategoryTotalSerializer(many=True)
