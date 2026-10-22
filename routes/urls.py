from django.urls import path

from .views import (
    HealthView,
    OptimizeRouteView,
    TravelEventsListView,
    VoiceQueryView,
    BolnaWebhookView,
)

urlpatterns = [
    path(
        "health/",
        HealthView.as_view(),
        name="health",
    ),
    path(
        "v1/routes/optimize/",
        OptimizeRouteView.as_view(),
        name="optimize-route",
    ),
    path(
        "v1/events/",
        TravelEventsListView.as_view(),
        name="travel-events",
    ),
    path(
        "v1/voice/query/",
        VoiceQueryView.as_view(),
        name="voice-query",
    ),
    path(
        "v1/bolna/webhook/",
        BolnaWebhookView.as_view(),
        name="bolna-webhook",
    ),
]
