from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.finance.services.reports import monthly_balance
from apps.finance.models import Transaction
from apps.finance.services.permissions import get_entities_for_user
from typing import cast
from django.contrib.auth.models import AbstractUser

class MonthlyBalanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = cast(AbstractUser, self.request.user)
        entities = get_entities_for_user(user)
        return (
            Transaction.objects
            .filter(entity__in=entities)
            .order_by("-date")
        )

