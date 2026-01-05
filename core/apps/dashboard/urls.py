from django.urls import path
from .views import dashboard, close_period_view, close_missing_periods_view

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("close-period/", close_period_view, name="close_period"),
    path("close-missing-periods/", close_missing_periods_view, name="close_missing_periods"),
]
