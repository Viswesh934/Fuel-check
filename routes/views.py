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
from routes.services.copilot_services import (
    HotelBookingService,
    HospitalService,
    MechanicService,
    ParcelService,
    EmergencyService,
)
from routes.services.weather_service import analyze_route_weather_hazards
from routes.services.fuel_price_service import FuelPriceService
from .models import FuelStation
from .serializers import OptimizeRouteSerializer, VoiceQuerySerializer, VoiceTTSSerializer

logger = logging.getLogger(__name__)


def get_route_cache_key(start: str, finish: str, language: str = "en") -> str:
    norm = f"{start.strip().lower()}|{finish.strip().lower()}|{language.strip().lower()}"
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    return f"route_opt:{digest}"


class HealthView(APIView):
    def get(self, request):
        return Response({
            "status": "ok",
            "service": "Fuel Check & Disha Compass Co-Pilot",
            "version": "2.5.0",
        })


class OptimizeRouteView(APIView):
    """
    Computes optimal route, fuel stops, road hazards, and co-pilot services
    (hotels, mechanics, parcels) along the corridor.
    """

    def post(self, request):
        serializer = OptimizeRouteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        start_location = serializer.validated_data["start"]
        finish_location = serializer.validated_data["finish"]
        language = serializer.validated_data.get("language", "en")

        cache_key = get_route_cache_key(start_location, finish_location, language)
        cache_ttl = getattr(settings, "ROUTE_CACHE_TTL", getattr(settings, "ROUTE_CACHE_TTL_SECONDS", 3600))
        cached_response = cache.get(cache_key)

        if cached_response is not None:
            resp = Response(cached_response["data"], status=cached_response["status"])
            resp["X-Cache"] = "HIT"
            return resp

        try:
            geocoder = GeocodingService()
            start = geocoder.geocode(start_location)
            finish = geocoder.geocode(finish_location)

            router = RoutingService()
            route = router.get_route(
                (start["longitude"], start["latitude"]),
                (finish["longitude"], finish["latitude"]),
            )

            distance_miles = route["distance_meters"] / 1609.344
            duration_minutes = route["duration_seconds"] / 60
            route_points = build_route_points(route["geometry"], distance_miles)

            station_service = FuelStationService()
            candidates = station_service.get_candidate_stations_for_route(
                route_points,
                distance_miles,
            )

            nodes = build_route_nodes(candidates, distance_miles)
            graph = build_route_graph(nodes)
            optimization = optimize_route(nodes, graph)
            optimization_result = build_optimization_result(optimization, nodes, graph)

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
                return Response(err_data, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

            fuel_consumed = distance_miles / 10.0

            # Travel Events & Hazard Matching
            event_service = TravelEventService()
            event_match_result = event_service.match_events_to_route(
                route_points,
                distance_miles,
            )
            matched_events = event_match_result["matched_events"]

            # Grounded Co-Pilot Advisory
            advisor_service = BedrockAdvisorService()
            route_summary = {
                "start_label": start["label"],
                "finish_label": finish["label"],
                "distance_miles": round(distance_miles, 1),
                "duration_minutes": round(duration_minutes, 1),
            }
            # Live Indian OMC Fuel Rates & Interstate VAT Arbitrage (Zero API Keys)
            fuel_price_service = FuelPriceService()
            raw_stops = optimization_result["stops"]
            enriched_stops = [fuel_price_service.enrich_station_with_live_price(s) for s in raw_stops]
            fuel_strategy = fuel_price_service.generate_fuel_savings_strategy(enriched_stops, language=language)

            advisory = advisor_service.generate_advisory(
                route_summary=route_summary,
                matched_events=matched_events,
                fuel_stops=enriched_stops,
                language=language,
            )
            # If border savings strategy exists, append to co-pilot advisory
            if fuel_strategy.get("has_strategy") and fuel_strategy.get("advisory"):
                advisory["message"] = f"{advisory['message']} {fuel_strategy['advisory']}"

            # Pre-synthesize Indic voice audio only if explicitly requested;
            # otherwise return immediately for sub-second responses (frontend fetches on-demand via /api/v1/voice/tts/)
            include_audio = serializer.validated_data.get("include_audio", False)
            if include_audio:
                audio_b64 = advisor_service.generate_speech_audio(
                    advisory.get("message", ""),
                    language=language,
                )
            else:
                audio_b64 = None
            advisory["audio_base64"] = audio_b64

            # Co-Pilot Corridor Amenities: Hotels, Hospitals, Mechanics, Freight Parcels
            hotel_service = HotelBookingService()
            hospital_service = HospitalService()
            mechanic_service = MechanicService()
            parcel_service = ParcelService()

            corridor_hotels = hotel_service.get_hotels_for_route(route_points, distance_miles)
            corridor_hospitals = hospital_service.get_hospitals_for_route(route_points, distance_miles)
            corridor_mechanics = mechanic_service.get_mechanics_for_route(route_points, distance_miles)
            corridor_parcels = parcel_service.get_parcels_for_route(route_points, distance_miles)

            # Live Open-Meteo Weather Hazards along Corridor Checkpoints
            weather_analysis = analyze_route_weather_hazards(route_points)
            live_wx_hazards = weather_analysis.get("weather_hazards", [])
            combined_alerts = list(matched_events) + live_wx_hazards
            total_delays = event_match_result["total_delay_minutes"] + sum(
                h.get("estimated_delay_minutes", 0) for h in live_wx_hazards
            )

            response_data = {
                "route": {
                    "distance_miles": round(distance_miles, 2),
                    "duration_minutes": round(duration_minutes, 2),
                    "start": {
                        "latitude": start["latitude"],
                        "longitude": start["longitude"],
                        "label": start["label"],
                    },
                    "finish": {
                        "latitude": finish["latitude"],
                        "longitude": finish["longitude"],
                        "label": finish["label"],
                    },
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
                "fuel_stops": enriched_stops,
                "live_fuel_strategy": fuel_strategy,
                "live_state_rates": fuel_price_service.get_live_fuel_rates(),
                "legs": optimization_result["legs"],
                "travel_events": {
                    "has_alerts": bool(combined_alerts),
                    "total_delay_minutes": total_delays,
                    "active_route_alerts": combined_alerts,
                    "all_candidate_events": event_match_result["all_events"],
                },
                "copilot_advisory": {
                    "message": advisory["message"],
                    "audio_base64": advisory.get("audio_base64"),
                    "llm_used": advisory["llm_used"],
                    "model": advisory["model"],
                },
                "copilot_amenities": {
                    "hotels": corridor_hotels,
                    "hospitals": corridor_hospitals,
                    "mechanics": corridor_mechanics,
                    "parcels": corridor_parcels,
                },
                "live_weather": weather_analysis,
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
    Voice Interaction endpoint for driver queries (hotel bookings, mechanics, parcels, SOS, fuel).
    """

    def post(self, request):
        serializer = VoiceQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        query = serializer.validated_data["query"]
        start = serializer.validated_data.get("start", "Delhi")
        finish = serializer.validated_data.get("finish", "Mumbai")
        language = serializer.validated_data.get("language", "en")

        cache_norm = f"{query.strip().lower()}|{start.strip().lower()}|{finish.strip().lower()}|{language.strip().lower()}"
        cache_key = f"voice_q:{hashlib.sha256(cache_norm.encode('utf-8')).hexdigest()}"
        cached = cache.get(cache_key)
        if cached is not None:
            resp = Response(cached, status=status.HTTP_200_OK)
            resp["X-Cache"] = "HIT"
            return resp

        try:
            bolna = BolnaVoiceService()
            result = bolna.answer_voice_query(query, start, finish, language=language)
            cache_ttl = getattr(settings, "ROUTE_CACHE_TTL", getattr(settings, "ROUTE_CACHE_TTL_SECONDS", 3600))
            cache.set(cache_key, result, timeout=cache_ttl)
            resp = Response(result, status=status.HTTP_200_OK)
            resp["X-Cache"] = "MISS"
            return resp
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


class VoiceTTSView(APIView):
    """
    Dedicated speech synthesis endpoint powered by Sarvam bulbul:v4-flash.
    Strictly isolated native speakers:
      - te-IN: kavitha_te_conversation (Pure Telugu)
      - ta-IN: gokul_ta_narration (Pure Tamil)
      - hi-IN: aditya_hi_conversational (Pure Hindi)
      - en-IN: simran_en_automobile (Pure English)
    """

    def post(self, request):
        serializer = VoiceTTSSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        text = serializer.validated_data["text"]
        language = serializer.validated_data.get("language", "en")

        advisor = BedrockAdvisorService()
        audio_b64 = advisor.generate_speech_audio(text, language=language)
        return Response({
            "status": "success",
            "language": language,
            "text": text,
            "audio_base64": audio_b64,
        }, status=status.HTTP_200_OK)


class LiveFuelRatesView(APIView):
    """
    Zero-key public endpoint returning daily 6:00 AM state-by-state diesel and petrol rates,
    state VAT tiers, and border arbitrage tips for commercial truckers.
    """

    def get(self, request):
        service = FuelPriceService()
        rates = service.get_live_fuel_rates()
        return Response({
            "status": "success",
            "date": "daily_6am_omc_revision",
            "currency": "INR (₹/L)",
            "state_rates": rates,
            "corridor_note": "Interstate diesel rates vary by state VAT (Delhi/Haryana lowest, Maharashtra highest).",
        }, status=status.HTTP_200_OK)


# Co-Pilot Dedicated REST APIs: Hotels, Mechanics, Parcels, SOS

class CopilotHotelBookView(APIView):
    def post(self, request):
        hotel_id = request.data.get("hotel_id", "HTL-5501")
        guest_name = request.data.get("guest_name", "Commercial Driver")
        rooms = int(request.data.get("rooms", 1))
        service = HotelBookingService()
        result = service.book_hotel(hotel_id=hotel_id, guest_name=guest_name, rooms=rooms)
        return Response(result, status=status.HTTP_200_OK)


class CopilotHospitalAlertView(APIView):
    def post(self, request):
        hospital_id = request.data.get("hospital_id", "HSP-5501")
        condition = request.data.get("condition", "Driver Emergency Alert")
        service = HospitalService()
        result = service.alert_emergency_room(hospital_id=hospital_id, medical_condition=condition)
        return Response(result, status=status.HTTP_200_OK)


class CopilotMechanicRequestView(APIView):
    def post(self, request):
        mechanic_id = request.data.get("mechanic_id", "MCH-5501")
        issue = request.data.get("issue", "Flat Tyre / Roadside Breakdown")
        service = MechanicService()
        result = service.request_mechanic(mechanic_id=mechanic_id, issue_type=issue)
        return Response(result, status=status.HTTP_200_OK)


class CopilotParcelDropView(APIView):
    def post(self, request):
        tracking_id = request.data.get("tracking_id", "TRK-IND-8821")
        notes = request.data.get("notes", "Delivered at warehouse dock")
        service = ParcelService()
        result = service.confirm_drop(tracking_id=tracking_id, notes=notes)
        return Response(result, status=status.HTTP_200_OK)


class CopilotSOSView(APIView):
    def post(self, request):
        lat = float(request.data.get("latitude", 38.6270))
        lng = float(request.data.get("longitude", -90.1994))
        service = EmergencyService()
        result = service.trigger_emergency_sos(latitude=lat, longitude=lng)
        return Response(result, status=status.HTTP_200_OK)



from routes.services.manifest_service import TripManifestService


class TripManifestExportView(APIView):
    """
    Exports a structured commercial waybill & dispatch manifest (Bilti)
    aggregating route checkpoints, diesel savings, emergency contacts, and active hazards.
    """

    def post(self, request):
        route_data = request.data.get("route_data")
        manifest_service = TripManifestService()

        if route_data and isinstance(route_data, dict):
            manifest = manifest_service.generate_manifest(route_data)
            return Response(manifest, status=status.HTTP_200_OK)

        start_loc = request.data.get("start", "Delhi")
        finish_loc = request.data.get("finish", "Mumbai")
        language = request.data.get("language", "en")

        cache_key = get_route_cache_key(start_loc, finish_loc, language)
        cached_response = cache.get(cache_key)

        if cached_response and "data" in cached_response:
            manifest = manifest_service.generate_manifest(cached_response["data"])
            return Response(manifest, status=status.HTTP_200_OK)

        opt_view = OptimizeRouteView()
        opt_res = opt_view.post(request)
        if opt_res.status_code == status.HTTP_200_OK:
            manifest = manifest_service.generate_manifest(opt_res.data)
            return Response(manifest, status=status.HTTP_200_OK)

        return opt_res
