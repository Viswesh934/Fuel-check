from django.urls import path
from .views import HealthView,DbCheckView

urlpatterns=[
    path("health/", HealthView.as_view()),
    path("db-check/", DbCheckView.as_view())
]