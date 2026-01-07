from rest_framework.permissions import BasePermission
class HasOrganizationAccess(BasePermission):
    message = "Debe indicar una organización activa."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and hasattr(request, 'organization')
            and request.organization is not None
        )