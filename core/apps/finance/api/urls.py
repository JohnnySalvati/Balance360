from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.finance.api.views.transaction import TransactionViewSet
from apps.finance.api.views.reports import MonthlyBalanceView

router = DefaultRouter()
router.register("transactions", TransactionViewSet, basename="transactions")

urlpatterns = [
    path("", include(router.urls)),
    path("reports/monthly/<int:entity_id>/", MonthlyBalanceView.as_view()),
]
