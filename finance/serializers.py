from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import serializers

from .models import Category, Transaction, Wallet


ZERO = Decimal("0.00")


# ======================== YORDAMCHI MAYDON ========================

class UserOwnedPrimaryKeyField(serializers.PrimaryKeyRelatedField):
    """
    Faqat joriy foydalanuvchiga tegishli obyektlarni qabul qiladi.
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        request = self.context.get("request")

        if request is None or not request.user.is_authenticated:
            return queryset.none()

        return queryset.filter(user=request.user)


# ======================== KATEGORIYA ========================

class CategorySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=100)
    type = serializers.ChoiceField(choices=Category.Type.choices)
    created_at = serializers.DateTimeField(read_only=True)

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Kategoriya nomi bo'sh bo'lmasligi kerak."
            )

        return value

    def validate(self, attrs):
        user = self.context["request"].user

        name = attrs.get(
            "name",
            self.instance.name if self.instance else None,
        )
        type_ = attrs.get(
            "type",
            self.instance.type if self.instance else None,
        )

        qs = Category.objects.filter(
            user=user,
            name__iexact=name,
            type=type_,
        )

        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError({
                "name": "Bunday nomli kategoriya allaqachon mavjud."
            })

        if (
            self.instance
            and type_ != self.instance.type
            and self.instance.transactions.exists()
        ):
            raise serializers.ValidationError({
                "type": "Tranzaksiyasi bor kategoriya turini o'zgartirib bo'lmaydi."
            })

        return attrs

    def create(self, validated_data):
        return Category.objects.create(
            user=self.context["request"].user,
            **validated_data,
        )

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()
        return instance

    @staticmethod
    def ensure_deletable(instance):
        if instance.transactions.exists():
            raise serializers.ValidationError({
                "detail": "Bu kategoriyada tranzaksiyalar bor. Avval ularni o'chiring."
            })


# ======================== HAMYON ========================

class WalletSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=100)
    currency = serializers.ChoiceField(
        choices=Wallet.Currency.choices,
        required=False,
    )
    balance = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=ZERO,
        required=False,
        help_text="Boshlang'ich balans. Keyin tranzaksiyalar orqali o'zgaradi.",
    )
    created_at = serializers.DateTimeField(read_only=True)

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Hamyon nomi bo'sh bo'lmasligi kerak."
            )

        return value

    def validate(self, attrs):
        user = self.context["request"].user

        if self.instance and "balance" in attrs:
            raise serializers.ValidationError({
                "balance": "Balansni to'g'ridan-to'g'ri o'zgartirib bo'lmaydi."
            })

        if "name" in attrs:
            qs = Wallet.objects.filter(
                user=user,
                name__iexact=attrs["name"],
            )

            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise serializers.ValidationError({
                    "name": "Bunday nomli hamyon allaqachon mavjud."
                })

        if (
            self.instance
            and "currency" in attrs
            and attrs["currency"] != self.instance.currency
            and self.instance.transactions.exists()
        ):
            raise serializers.ValidationError({
                "currency": "Tranzaksiyasi bor hamyon valyutasini o'zgartirib bo'lmaydi."
            })

        return attrs

    def create(self, validated_data):
        return Wallet.objects.create(
            user=self.context["request"].user,
            name=validated_data["name"],
            currency=validated_data.get(
                "currency",
                Wallet.Currency.UZS,
            ),
            balance=validated_data.get("balance", ZERO),
        )

    def update(self, instance, validated_data):
        for field in ("name", "currency"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        instance.save()
        return instance


# ======================== TRANZAKSIYA ========================

class TransactionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)

    wallet = UserOwnedPrimaryKeyField(
        queryset=Wallet.objects.all(),
    )
    category = UserOwnedPrimaryKeyField(
        queryset=Category.objects.all(),
    )

    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    description = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )
    date = serializers.DateField(
        required=False,
        help_text="Kiritilmasa bugungi sana olinadi.",
    )

    type = serializers.CharField(
        source="category.type",
        read_only=True,
    )
    wallet_name = serializers.CharField(
        source="wallet.name",
        read_only=True,
    )
    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
    )
    created_at = serializers.DateTimeField(read_only=True)

    def validate_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError(
                "Kelajak sanasini kiritib bo'lmaydi."
            )

        return value

    @staticmethod
    def get_delta(category, amount):
        if category.type == Category.Type.INCOME:
            return amount

        return -amount

    @staticmethod
    def lock_wallet(wallet_id):
        return Wallet.objects.select_for_update().get(pk=wallet_id)

    @transaction.atomic
    def create(self, validated_data):
        wallet = self.lock_wallet(
            validated_data["wallet"].pk
        )
        category = validated_data["category"]
        amount = validated_data["amount"]

        wallet.balance += self.get_delta(category, amount)

        if wallet.balance < ZERO:
            raise serializers.ValidationError({
                "amount": "Hamyonda mablag' yetarli emas."
            })

        wallet.save(update_fields=["balance"])

        return Transaction.objects.create(
            user=self.context["request"].user,
            wallet=wallet,
            category=category,
            amount=amount,
            description=validated_data.get("description", ""),
            date=validated_data.get(
                "date",
                timezone.localdate(),
            ),
        )

    @transaction.atomic
    def update(self, instance, validated_data):
        old_wallet_id = instance.wallet_id
        new_wallet_id = validated_data.get(
            "wallet",
            instance.wallet,
        ).pk

        # Bir nechta hamyon bo'lsa, ularni bir xil tartibda bloklaymiz.
        wallet_ids = sorted(set([old_wallet_id, new_wallet_id]))
        wallets = {
            wallet.pk: wallet
            for wallet in Wallet.objects.select_for_update()
            .filter(pk__in=wallet_ids)
            .order_by("pk")
        }

        old_wallet = wallets[old_wallet_id]
        new_wallet = wallets[new_wallet_id]

        category = validated_data.get(
            "category",
            instance.category,
        )
        amount = validated_data.get(
            "amount",
            instance.amount,
        )

        # Eski tranzaksiya ta'sirini qaytaramiz.
        old_wallet.balance -= instance.signed_amount

        # Yangi tranzaksiya ta'sirini qo'llaymiz.
        new_wallet.balance += self.get_delta(category, amount)

        if old_wallet.balance < ZERO or new_wallet.balance < ZERO:
            raise serializers.ValidationError({
                "amount": "O'zgartirishdan so'ng balans manfiy bo'lib qoladi."
            })

        old_wallet.save(update_fields=["balance"])

        if new_wallet.pk != old_wallet.pk:
            new_wallet.save(update_fields=["balance"])

        instance.wallet = new_wallet
        instance.category = category
        instance.amount = amount
        instance.description = validated_data.get(
            "description",
            instance.description,
        )
        instance.date = validated_data.get(
            "date",
            instance.date,
        )

        instance.save()
        return instance

    @staticmethod
    @transaction.atomic
    def delete_instance(instance):
        wallet = Wallet.objects.select_for_update().get(
            pk=instance.wallet_id
        )

        wallet.balance -= instance.signed_amount

        if wallet.balance < ZERO:
            raise serializers.ValidationError({
                "detail": "Tranzaksiyani o'chirishdan keyin balans manfiy bo'ladi."
            })

        wallet.save(update_fields=["balance"])
        instance.delete()


# ======================== TRANZAKSIYA FILTRLARI ========================

class TransactionFilterSerializer(serializers.Serializer):
    ORDERING_CHOICES = [
        "date",
        "-date",
        "amount",
        "-amount",
        "created_at",
        "-created_at",
    ]

    type = serializers.ChoiceField(
        choices=Category.Type.choices,
        required=False,
    )
    category = serializers.IntegerField(required=False)
    wallet = serializers.IntegerField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    min_amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
    )
    max_amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
    )
    search = serializers.CharField(required=False)
    ordering = serializers.ChoiceField(
        choices=ORDERING_CHOICES,
        required=False,
    )

    def validate(self, attrs):
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")

        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError({
                "date_from": "Boshlanish sanasi tugash sanasidan katta bo'lmasligi kerak."
            })

        min_amount = attrs.get("min_amount")
        max_amount = attrs.get("max_amount")

        if (
            min_amount is not None
            and max_amount is not None
            and min_amount > max_amount
        ):
            raise serializers.ValidationError({
                "min_amount": "Minimal summa maksimal summadan katta bo'lmasligi kerak."
            })

        return attrs

    def filter_queryset(self, queryset):
        data = self.validated_data

        if "type" in data:
            queryset = queryset.filter(
                category__type=data["type"]
            )

        if "category" in data:
            queryset = queryset.filter(
                category_id=data["category"]
            )

        if "wallet" in data:
            queryset = queryset.filter(
                wallet_id=data["wallet"]
            )

        if "date_from" in data:
            queryset = queryset.filter(
                date__gte=data["date_from"]
            )

        if "date_to" in data:
            queryset = queryset.filter(
                date__lte=data["date_to"]
            )

        if "min_amount" in data:
            queryset = queryset.filter(
                amount__gte=data["min_amount"]
            )

        if "max_amount" in data:
            queryset = queryset.filter(
                amount__lte=data["max_amount"]
            )

        if data.get("search"):
            queryset = queryset.filter(
                description__icontains=data["search"]
            )

        if "ordering" in data:
            queryset = queryset.order_by(
                data["ordering"],
                "-id",
            )

        return queryset


# ======================== STATISTIKA SO'ROVI ========================

class SummaryQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    wallet = UserOwnedPrimaryKeyField(
        queryset=Wallet.objects.all(),
        required=False,
    )

    def validate(self, attrs):
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")

        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError({
                "date_from": "Boshlanish sanasi tugash sanasidan katta bo'lmasligi kerak."
            })

        return attrs

    def build(self, user):
        data = self.validated_data

        queryset = Transaction.objects.filter(user=user)

        if "wallet" in data:
            queryset = queryset.filter(
                wallet=data["wallet"]
            )

        if "date_from" in data:
            queryset = queryset.filter(
                date__gte=data["date_from"]
            )

        if "date_to" in data:
            queryset = queryset.filter(
                date__lte=data["date_to"]
            )

        totals = queryset.aggregate(
            total_income=Sum(
                "amount",
                filter=Q(
                    category__type=Category.Type.INCOME
                ),
            ),
            total_expense=Sum(
                "amount",
                filter=Q(
                    category__type=Category.Type.EXPENSE
                ),
            ),
            transactions_count=Count("id"),
        )

        income = totals["total_income"] or ZERO
        expense = totals["total_expense"] or ZERO

        rows = (
            queryset.values(
                "category_id",
                "category__name",
                "category__type",
            )
            .annotate(
                total=Sum("amount"),
                count=Count("id"),
            )
            .order_by("category__type", "-total")
        )

        categories = [
            {
                "category": row["category_id"],
                "name": row["category__name"],
                "type": row["category__type"],
                "total": row["total"],
                "count": row["count"],
            }
            for row in rows
        ]

        return {
            "total_income": income,
            "total_expense": expense,
            "balance": income - expense,
            "transactions_count": totals["transactions_count"],
            "categories": categories,
        }


# ======================== STATISTIKA NATIJASI ========================

class CategoryTotalSerializer(serializers.Serializer):
    category = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.ChoiceField(
        choices=Category.Type.choices
    )
    total = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    count = serializers.IntegerField()


class SummaryResponseSerializer(serializers.Serializer):
    total_income = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    total_expense = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    balance = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    transactions_count = serializers.IntegerField()
    categories = CategoryTotalSerializer(many=True)