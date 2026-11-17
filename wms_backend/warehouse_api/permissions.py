from rest_framework.permissions import BasePermission, SAFE_METHODS

from warehouse_api.models import User


class ReadOnlyOrAdminManager(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role in {User.Role.ADMIN, User.Role.MANAGER}


class OperatorOrAbove(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role != User.Role.VIEWER
        )


class AdminOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.ADMIN
        )


class ManagerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {User.Role.ADMIN, User.Role.MANAGER}
        )


class ViewerReadOnly(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role != User.Role.VIEWER
