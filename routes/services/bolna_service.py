import logging
from typing import Dict, Any, Optional
from django.conf import settings

from .routing import RoutingService
from .geocoding import GeocodingService
from .route_geometry import build_route_points
from .station_service import FuelStationService
from .route_graph import build_route_nodes, build_route_graph
from .optimizer import optimize_route, build_optimization_result
from .travel_events import TravelEventService
from .bedrock_service import BedrockAdvisorService

logger = logging.getLogger(__name__)


class BolnaVoiceService:
    """
    Bolna Voice Agent Integration Service.
    Enables voice agents to retrieve deterministic route data and grounded travel advisories
    from Fuel Check backend tools.
    """

    def __init__(self):
        self.api_key = getattr(settings, "BOLNA_API_KEY", "")
        self.agent_id = getattr(settings, "BOLNA_AGENT_ID", "")
        self.geocoder = GeocodingService()
        self.router = RoutingService()
        self.station_service = FuelStationService()
        self.event_service = TravelEventService()
        self.advisor = BedrockAdvisorService()

    def answer_voice_query(
        self,
        query: str,
        start_location: str,
        finish_location: str,
    ) -> Dict[str, Any]:
        """
        Processes a driver's spoken query (e.g., "What does this event mean for my route?")
        Grounded strictly in Fuel Check's backend truth.
        """
        # 1. Geocode locations
        start = self.geocoder.geocode(start_location)
        finish = self.geocoder.geocode(finish_location)

        # 2. Compute driving route
        route = self.router.get_route(
            (start["longitude"], start["latitude"]),
            (finish["longitude"], finish["latitude"]),
        )
        distance_miles = route["distance_meters"] / 1609.344
        duration_minutes = route["duration_seconds"] / 60

        # 3. Geometry points
        route_points = build_route_points(route["geometry"], distance_miles)

        # 4. Fuel stops calculation
        candidates = self.station_service.get_candidate_stations_for_route(
            route_points, distance_miles
        )
        nodes = build_route_nodes(candidates, distance_miles)
        graph = build_route_graph(nodes)
        optimization = optimize_route(nodes, graph)
        opt_result = build_optimization_result(optimization, nodes, graph)
        stops = opt_result["stops"] if opt_result else []

        # 5. Deterministic route-aware event matching
        event_match = self.event_service.match_events_to_route(route_points, distance_miles)
        matched_events = event_match["matched_events"]

        route_summary = {
            "start_label": start["label"],
            "finish_label": finish["label"],
            "distance_miles": round(distance_miles, 1),
            "duration_minutes": round(duration_minutes, 1),
        }

        # 6. Generate grounded voice advisory (Conditional AI via Bedrock)
        advisory_result = self.advisor.generate_advisory(
            route_summary=route_summary,
            matched_events=matched_events,
            fuel_stops=stops,
            user_query=query,
        )

        return {
            "query": query,
            "spoken_answer": advisory_result["message"],
            "affects_route": event_match["has_matching_events"],
            "matched_events_count": len(matched_events),
            "matched_events": matched_events,
            "total_delay_minutes": event_match["total_delay_minutes"],
            "fuel_stops_count": len(stops),
            "fuel_stops": stops,
            "llm_used": advisory_result["llm_used"],
            "ai_model": advisory_result["model"],
            "route_summary": route_summary,
        }

    def handle_bolna_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatcher for Bolna tool / function calling webhooks.
        """
        tool_name = payload.get("tool_name") or payload.get("name") or "get_travel_advisory"
        arguments = payload.get("arguments") or payload.get("parameters") or payload

        start = arguments.get("start", "Chicago, IL")
        finish = arguments.get("finish", "Little Rock, AR")
        query = arguments.get("query", "What does this event mean for my route?")

        result = self.answer_voice_query(query, start, finish)

        return {
            "status": "success",
            "tool": tool_name,
            "data": result,
            "audio_speech_text": result["spoken_answer"],
        }
