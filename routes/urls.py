from django.urls import path

from .views import (
    HealthView,
    OptimizeRouteView,
)

urlpatterns = [
    path(
        "health/",
        HealthView.as_view(),
    ),
    path(
        "v1/routes/optimize/",
        OptimizeRouteView.as_view(),
    ),
]