from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    


    message = "Bu obyekt sizga tegishli emas."

    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.id


class IsActiveUser(BasePermission):
    

    message = "Akkauntingiz faol emas."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)
