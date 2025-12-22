from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from apps.finance.models import Transaction
from apps.finance.api.serializers.transaction import TransactionSerializer
from apps.finance.services.permissions import get_entities_for_user
from apps.accounts.models import User 

class TransactionViewSet(ModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post"]

    def get_queryset(self):
        user = self.request.user

        if not isinstance(user, User):
            return Transaction.objects.none()

        entities = get_entities_for_user(user)
        return (
            Transaction.objects
            .filter(entity_id__in=entities)
            .order_by("-date")
        )
