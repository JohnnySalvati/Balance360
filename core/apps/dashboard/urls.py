from django.urls import path
from .views import dashboard, close_period_view

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("close-period/", close_period_view, name="close_period"),
]
