from django.urls import path
from .views import HealthView,DbCheckView,RouteTestView

urlpatterns=[
    path("health/", HealthView.as_view()),
    path("db-check/", DbCheckView.as_view()),
    path("route-test/", RouteTestView.as_view()),
]