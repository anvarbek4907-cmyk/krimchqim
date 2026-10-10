from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """Obyekt (kategoriya, hamyon, tranzaksiya) faqat o'z egasiga ruxsat etiladi.

    Queryset allaqachon foydalanuvchi bo'yicha filtrlanadi; bu klass ikkinchi
    himoya qatlami bo'lib, kelajakda queryset noto'g'ri o'zgarib qolsa ham
    begona ma'lumotga kirishni to'sadi.
    """

    message = "Bu obyekt sizga tegishli emas."

    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.id


class IsActiveUser(BasePermission):
    """Faqat tizimga kirgan va bloklanmagan (is_active) foydalanuvchilar."""

    message = "Akkauntingiz faol emas."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)
