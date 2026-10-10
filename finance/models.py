from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Category(models.Model):
    """Kirim yoki chiqim kategoriyasi (masalan: Oylik, Oziq-ovqat)."""

    class Type(models.TextChoices):
        INCOME = "income", "Kirim"
        EXPENSE = "expense", "Chiqim"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=Type.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Kategoriya"
        verbose_name_plural = "Kategoriyalar"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name", "type"], name="unique_category_per_user"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"


class Wallet(models.Model):
    """Hamyon / hisob (naqd, karta va h.k.). Balans tranzaksiyalar bilan o'zgaradi."""

    class Currency(models.TextChoices):
        UZS = "UZS", "So'm"
        USD = "USD", "Dollar"
        EUR = "EUR", "Yevro"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallets"
    )
    name = models.CharField(max_length=100)
    currency = models.CharField(
        max_length=3, choices=Currency.choices, default=Currency.UZS
    )
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Hamyon"
        verbose_name_plural = "Hamyonlar"
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_wallet_per_user")
        ]

    def __str__(self):
        return f"{self.name}: {self.balance} {self.currency}"


class Transaction(models.Model):
    """Kirim yoki chiqim yozuvi. Turi (kirim/chiqim) kategoriyadan olinadi."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions"
    )
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="transactions"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Tranzaksiya"
        verbose_name_plural = "Tranzaksiyalar"

    def __str__(self):
        return f"{self.category.type} {self.amount} ({self.date})"

    @property
    def signed_amount(self):
        """Hamyon balansiga ta'siri: kirim = +, chiqim = -."""
        if self.category.type == Category.Type.INCOME:
            return self.amount
        return -self.amount
