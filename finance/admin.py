from django.contrib import admin

from .models import Category, Transaction, Wallet


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "type", "user", "created_at")
    list_filter = ("type",)
    search_fields = ("name", "user__username")


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "user", "currency", "balance", "created_at")
    list_filter = ("currency",)
    search_fields = ("name", "user__username")
    readonly_fields = ("balance",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "wallet", "category", "amount", "date")
    list_filter = ("category__type", "date")
    search_fields = ("description", "user__username", "category__name")
    date_hierarchy = "date"
    list_select_related = ("user", "wallet", "category")
с