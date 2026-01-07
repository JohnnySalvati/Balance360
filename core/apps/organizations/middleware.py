from django.http import JsonResponse

from .models import Membership
class OrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization = None
        request.membership = None

        org_id = request.headers.get('X-Organization-ID')
        if not org_id:
            return self.get_response(request)

        user = request.user
        if not user.is_authenticated:
            return self.get_response(request)

        try:
            membership = Membership.objects.select_related('organization').get(
                user=user,
                organization_id=org_id
            )
        except Membership.DoesNotExist:
            return JsonResponse(
                {'detail': 'No pertenece a la organización indicada'},
                status=403
            )

        request.organization = membership.organization
        request.membership = membership

        return self.get_response(request)
