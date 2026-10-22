import hashlib
import logging
from django.conf import settings
from django.core.cache import cache

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from routes.services.routing import RoutingService
from routes.services.geocoding import GeocodingService
from routes.services.route_geometry import build_route_points
from routes.services.station_service import FuelStationService
from routes.services.station_projection import find_candidate_stations
from routes.services.route_graph import (
    build_route_nodes,
    build_route_graph,
)
from routes.services.optimizer import (
    optimize_route,
    build_optimization_result,
)
from routes.services.travel_events import TravelEventService
from routes.services.bedrock_service import BedrockAdvisorService
from routes.services.bolna_service import BolnaVoiceService
from .models import FuelStation
from .serializers import OptimizeRouteSerializer, VoiceQuerySerializer

logger = logging.getLogger(__name__)


def get_route_cache_key(start: str, finish: str) -> str:
    norm = f"{start.strip().lower()}|{finish.strip().lower()}"
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    return f"route_opt:{digest}"


class HealthView(APIView):
    def get(self, request):
        return Response({
            "status": "ok",
            "service": "Fuel Check Travel Awareness Co-Pilot",
            "version": "2.0.0",
        })


class OptimizeRouteView(APIView):

    def post(self, request):
        serializer = OptimizeRouteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        start_location = serializer.validated_data["start"].strip()
        finish_location = serializer.validated_data["finish"].strip()

        cache_key = get_route_cache_key(start_location, finish_location)
        cached_entry = cache.get(cache_key)
        if cached_entry is not None:
            resp = Response(cached_entry["data"], status=cached_entry["status"])
            resp["X-Cache"] = "HIT"
            return resp

        try:
            # 1. Geocode user locations (using Nominatim / OpenStreetMap by default)
            geocoder = GeocodingService()
            start = geocoder.geocode(start_location)
            finish = geocoder.geocode(finish_location)

            # 2. Get route geometry (using OSRM directions by default)
            router = RoutingService()
            route = router.get_route(
                (start["longitude"], start["latitude"]),
                (finish["longitude"], finish["latitude"]),
            )

            distance_miles = route["distance_meters"] / 1609.344
            duration_minutes = route["duration_seconds"] / 60

            # 3. Convert route geometry to cumulative route miles
            route_points = build_route_points(
                route["geometry"],
                distance_miles,
            )

            # 4. Sourcing fuel stations (Decoupled from hardcoded SQL)
            station_service = FuelStationService()
            candidates = station_service.get_candidate_stations_for_route(
                route_points,
                distance_miles,
                tolerance_miles=5.0,
            )

            # 5. Build reachability graph (500 miles max range constraint)
            nodes = build_route_nodes(
                candidates,
                distance_miles,
            )
            graph = build_route_graph(nodes)

            # 6. Dynamic Programming Optimizer
            optimization = optimize_route(
                nodes,
                graph,
            )

            # 7. Format fuel results
            optimization_result = build_optimization_result(
                optimization,
                nodes,
                graph,
            )

            cache_ttl = getattr(settings, "ROUTE_CACHE_TTL", 300)

            # 8. Check for infeasible route
            if optimization_result is None:
                err_data = {
                    "error": "No feasible fuel-stop plan exists for this route.",
                    "route": {
                        "distance_miles": round(distance_miles, 2),
                        "duration_minutes": round(duration_minutes, 2),
                    },
                }
                cache.set(
                    cache_key,
                    {"data": err_data, "status": status.HTTP_422_UNPROCESSABLE_ENTITY},
                    timeout=cache_ttl,
                )
                resp = Response(err_data, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
                resp["X-Cache"] = "MISS"
                return resp

            # 9. Deterministic route-aware travel event matching (Normal code, NOT LLM)
            event_service = TravelEventService()
            event_match_result = event_service.match_events_to_route(
                route_points,
                distance_miles,
            )

            matched_events = event_match_result["matched_events"]

            # 10. Conditional AI usage via AWS Bedrock
            # Rule: If no matching condition, NO LLM call is made (cost-conscious)
            advisor = BedrockAdvisorService()
            route_summary = {
                "start_label": start.get("label", start_location),
                "finish_label": finish.get("label", finish_location),
                "distance_miles": round(distance_miles, 2),
                "duration_minutes": round(duration_minutes, 2),
            }
            advisory = advisor.generate_advisory(
                route_summary=route_summary,
                matched_events=matched_events,
                fuel_stops=optimization_result["stops"],
            )

            fuel_consumed = distance_miles / 10

            response_data = {
                "start": start,
                "finish": finish,

                "route": {
                    "distance_miles": round(distance_miles, 2),
                    "duration_minutes": round(duration_minutes, 2),
                    "geometry": route["geometry"],
                },

                "fuel": {
                    "mpg": 10,
                    "max_range_miles": 500,
                    "consumed_gallons": round(fuel_consumed, 2),
                    "starting_fuel_gallons": 50,
                    "modeled_purchased_gallons": round(
                        optimization_result["total_gallons_purchased"],
                        2,
                    ),
                    "total_cost": round(
                        optimization_result["total_cost"],
                        2,
                    ),
                },

                "fuel_stops": optimization_result["stops"],
                "legs": optimization_result["legs"],

                # Travel-Awareness Co-Pilot extensions
                "travel_events": {
                    "has_alerts": event_match_result["has_matching_events"],
                    "total_delay_minutes": event_match_result["total_delay_minutes"],
                    "active_route_alerts": matched_events,
                    "all_candidate_events": event_match_result["all_events"],
                },

                "copilot_advisory": {
                    "message": advisory["message"],
                    "llm_used": advisory["llm_used"],
                    "model": advisory["model"],
                },
            }

            cache.set(
                cache_key,
                {"data": response_data, "status": status.HTTP_200_OK},
                timeout=cache_ttl,
            )

            resp = Response(response_data, status=status.HTTP_200_OK)
            resp["X-Cache"] = "MISS"
            return resp

        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as exc:
            logger.exception("OptimizeRouteView unexpected exception")
            return Response(
                {"error": "Unable to calculate route."},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class TravelEventsListView(APIView):
    """
    Returns all registered travel events and fixtures, clearly marking
    simulated demo events vs verified live events.
    """

    def get(self, request):
        service = TravelEventService()
        events = [e.to_dict() for e in service.get_all_events()]
        return Response({
            "count": len(events),
            "events": events,
            "disclaimer": "Simulated fixtures are explicitly labeled and must never be presented as verified real-world incidents.",
        })


class VoiceQueryView(APIView):
    """
    Voice Interaction endpoint for driver queries (e.g. "What does this event mean for my route?")
    Grounded strictly in Fuel Check backend data and invoking Bedrock conditionally.
    """

    def post(self, request):
        serializer = VoiceQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        query = serializer.validated_data["query"]
        start = serializer.validated_data.get("start", "Chicago, IL")
        finish = serializer.validated_data.get("finish", "Little Rock, AR")

        try:
            bolna = BolnaVoiceService()
            result = bolna.answer_voice_query(query, start, finish)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.exception("Voice query processing failed")
            return Response(
                {"error": f"Voice co-pilot error: {str(exc)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class BolnaWebhookView(APIView):
    """
    Standard tool-execution webhook for Bolna Voice Agents.
    """

    def post(self, request):
        try:
            bolna = BolnaVoiceService()
            result = bolna.handle_bolna_webhook(request.data)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.exception("Bolna webhook processing failed")
            return Response(
                {"status": "error", "message": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
