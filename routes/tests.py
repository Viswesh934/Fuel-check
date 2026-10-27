from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from routes.models import FuelStation
from routes.services.route_geometry import haversine_distance, build_route_points
from routes.services.station_projection import (
    find_station_position,
    deduplicate_candidates,
)
from routes.services.route_graph import build_route_graph
from routes.services.optimizer import optimize_route, build_optimization_result


class RouteGeometryTests(TestCase):
    def test_haversine_distance_same_point(self):
        dist = haversine_distance((-74.0, 40.0), (-74.0, 40.0))
        self.assertAlmostEqual(dist, 0.0, places=4)

    def test_haversine_distance_known_points(self):
        # NY (-74.006, 40.7128) to Philadelphia (-75.1652, 39.9526) as-the-crow-flies is ~61 miles
        dist = haversine_distance((-74.006, 40.7128), (-75.1652, 39.9526))
        self.assertTrue(55.0 < dist < 70.0)

    def test_build_route_points_normalization(self):
        geometry = {
            "type": "LineString",
            "coordinates": [
                [-87.6606, 41.8789],
                [-88.0000, 41.5000],
                [-89.0000, 40.5000],
                [-92.3558, 34.7136],
            ],
        }
        total_distance = 650.0
        points = build_route_points(geometry, total_distance)

        self.assertEqual(len(points), 4)
        self.assertAlmostEqual(points[0]["mile"], 0.0, places=4)
        self.assertAlmostEqual(points[-1]["mile"], total_distance, places=4)
        # Monotonically increasing
        for i in range(len(points) - 1):
            self.assertLess(points[i]["mile"], points[i + 1]["mile"])


class StationProjectionTests(TestCase):
    def setUp(self):
        # A simple straight west-to-east route from (-90.0, 35.0) to (-88.0, 35.0)
        # 1 deg longitude at lat 35 is ~56.6 miles
        self.route_points = [
            {"longitude": -90.0, "latitude": 35.0, "mile": 0.0},
            {"longitude": -89.0, "latitude": 35.0, "mile": 56.6},
            {"longitude": -88.0, "latitude": 35.0, "mile": 113.2},
        ]

    def test_station_within_tolerance(self):
        # Station directly on route at (-89.0, 35.0)
        station = FuelStation.objects.create(
            opis_truckstop_id=101,
            name="Near Station",
            city="Anytown",
            state="TN",
            retail_price=3.50,
            latitude=35.0,
            longitude=-89.0,
        )
        pos = find_station_position(station, self.route_points, tolerance_miles=5.0)
        self.assertIsNotNone(pos)
        self.assertAlmostEqual(pos["route_mile"], 56.6, delta=1.0)
        self.assertLess(pos["distance_to_route"], 0.5)

    def test_station_outside_tolerance_returns_none(self):
        # Station 1 degree (~69 miles) north of route
        station = FuelStation.objects.create(
            opis_truckstop_id=102,
            name="Far Station",
            city="FarCity",
            state="TN",
            retail_price=3.00,
            latitude=36.0,
            longitude=-89.0,
        )
        pos = find_station_position(station, self.route_points, tolerance_miles=5.0)
        self.assertIsNone(pos)

    def test_deduplicate_candidates(self):
        s1 = FuelStation.objects.create(
            opis_truckstop_id=103,
            name="Station A",
            retail_price=3.50,
            latitude=35.12345,
            longitude=-89.12345,
        )
        s2 = FuelStation.objects.create(
            opis_truckstop_id=104,
            name="Station A Duplicate",
            retail_price=3.40,
            latitude=35.123451,
            longitude=-89.123452,
        )
        candidates = [
            {"station": s1, "route_mile": 25.0, "distance_to_route": 1.0},
            {"station": s2, "route_mile": 25.0, "distance_to_route": 1.0},
        ]
        unique = deduplicate_candidates(candidates)
        self.assertEqual(len(unique), 1)


class RouteGraphAndOptimizationTests(TestCase):
    def test_reachability_threshold_500_vs_501(self):
        # Node at 0, one at 500, one at 501
        nodes = [
            {"id": "START", "type": "start", "route_mile": 0.0},
            {"id": "STATION_500", "type": "station", "route_mile": 500.0, "station": MagicMock(retail_price=3.00)},
            {"id": "STATION_501", "type": "station", "route_mile": 501.0, "station": MagicMock(retail_price=3.00)},
        ]
        graph = build_route_graph(nodes)

        # 500-mile leg is reachable from START
        reachable_from_start = [edge["to"] for edge in graph["START"]]
        self.assertIn("STATION_500", reachable_from_start)

        # 501-mile leg is unreachable from START
        self.assertNotIn("STATION_501", reachable_from_start)

    def test_forward_only_dag_edges(self):
        nodes = [
            {"id": "START", "type": "start", "route_mile": 0.0},
            {"id": "S1", "type": "station", "route_mile": 100.0, "station": MagicMock(retail_price=3.0)},
            {"id": "S2", "type": "station", "route_mile": 200.0, "station": MagicMock(retail_price=3.0)},
            {"id": "FINISH", "type": "finish", "route_mile": 300.0},
        ]
        graph = build_route_graph(nodes)

        # S2 cannot have an edge pointing backwards to S1 or START
        targets_from_s2 = [edge["to"] for edge in graph["S2"]]
        self.assertNotIn("S1", targets_from_s2)
        self.assertNotIn("START", targets_from_s2)
        self.assertIn("FINISH", targets_from_s2)

    def test_synthetic_cheapest_station_selected(self):
        """
        Total trip = 600 miles (> 500 mi max range, so direct leg impossible).
        At mile 300:
          - Station Expensive: $4.50/gal
          - Station Cheap:     $2.80/gal
        Leg from station to FINISH is 300 miles (30 gallons).
        Expected choice: Station Cheap.
        """
        station_expensive = MagicMock(id=1, name="Expensive Gas", city="CityA", state="IL", retail_price=4.50, latitude=40.1, longitude=-88.1)
        station_cheap = MagicMock(id=2, name="Cheap Gas", city="CityB", state="IL", retail_price=2.80, latitude=40.2, longitude=-88.2)

        nodes = [
            {"id": "START", "type": "start", "route_mile": 0.0},
            {"id": "STATION_EXP", "type": "station", "route_mile": 300.0, "station": station_expensive},
            {"id": "STATION_CHP", "type": "station", "route_mile": 300.0, "station": station_cheap},
            {"id": "FINISH", "type": "finish", "route_mile": 600.0},
        ]
        graph = build_route_graph(nodes)
        opt = optimize_route(nodes, graph)
        res = build_optimization_result(opt, nodes, graph)

        self.assertIsNotNone(res)
        self.assertEqual(res["path"], ["START", "STATION_CHP", "FINISH"])
        self.assertEqual(len(res["stops"]), 1)
        self.assertEqual(res["stops"][0]["id"], 2)
        self.assertEqual(res["stops"][0]["latitude"], 40.2)
        self.assertEqual(res["stops"][0]["longitude"], -88.2)
        # 300 miles / 10 mpg = 30 gallons * $2.80 = $84.00
        self.assertAlmostEqual(res["total_cost"], 84.00, places=2)
        self.assertAlmostEqual(res["total_gallons_purchased"], 30.00, places=2)

    def test_no_feasible_route_returns_none(self):
        """
        Total trip = 1200 miles with no stations reachable within 500 miles.
        """
        station_far = MagicMock(id=9, name="Far Gas", city="CityX", state="IL", retail_price=3.00)
        nodes = [
            {"id": "START", "type": "start", "route_mile": 0.0},
            {"id": "STATION_FAR", "type": "station", "route_mile": 600.0, "station": station_far},
            {"id": "FINISH", "type": "finish", "route_mile": 1200.0},
        ]
        graph = build_route_graph(nodes)
        opt = optimize_route(nodes, graph)
        res = build_optimization_result(opt, nodes, graph)

        self.assertIsNone(opt)
        self.assertIsNone(res)

    def test_direct_route_under_500_miles_has_zero_stops(self):
        """
        Route under 500 miles with full tank costs $0 and requires 0 fuel stops.
        """
        nodes = [
            {"id": "START", "type": "start", "route_mile": 0.0},
            {"id": "STATION_1", "type": "station", "route_mile": 150.0, "station": MagicMock(retail_price=3.50)},
            {"id": "FINISH", "type": "finish", "route_mile": 250.0},
        ]
        graph = build_route_graph(nodes)
        opt = optimize_route(nodes, graph)
        res = build_optimization_result(opt, nodes, graph)

        self.assertIsNotNone(res)
        self.assertEqual(res["path"], ["START", "FINISH"])
        self.assertEqual(len(res["stops"]), 0)
        self.assertEqual(res["total_cost"], 0.0)


class OptimizeRouteAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_missing_start_or_finish_returns_400(self):
        res = self.client.post("/api/v1/routes/optimize/", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start", res.data)
        self.assertIn("finish", res.data)

    def test_blank_location_returns_400(self):
        res = self.client.post(
            "/api/v1/routes/optimize/",
            {"start": "", "finish": "Chicago, IL"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("routes.views.GeocodingService")
    def test_invalid_location_geocoding_error_returns_400(self, mock_geocoder_cls):
        mock_geocoder = mock_geocoder_cls.return_value
        mock_geocoder.geocode.side_effect = ValueError("Location not found: InvalidCityXYZ")

        res = self.client.post(
            "/api/v1/routes/optimize/",
            {"start": "InvalidCityXYZ", "finish": "Chicago, IL"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", res.data)
        self.assertIn("Location not found", res.data["error"])

    @patch("routes.views.optimize_route")
    @patch("routes.views.RoutingService")
    @patch("routes.views.GeocodingService")
    def test_infeasible_route_returns_422(
        self,
        mock_geocoder_cls,
        mock_router_cls,
        mock_optimize_route,
    ):
        mock_geocoder = mock_geocoder_cls.return_value
        mock_geocoder.geocode.side_effect = [
            {"longitude": -74.0, "latitude": 40.7, "label": "New York, NY"},
            {"longitude": -87.6, "latitude": 41.8, "label": "Chicago, IL"},
        ]

        mock_router = mock_router_cls.return_value
        mock_router.get_route.return_value = {
            "distance_meters": 800 * 1609.344,
            "duration_seconds": 36000,
            "geometry": {"type": "LineString", "coordinates": [[-74.0, 40.7], [-87.6, 41.8]]},
        }

        # Optimizer returns None (no reachable path)
        mock_optimize_route.return_value = None

        res = self.client.post(
            "/api/v1/routes/optimize/",
            {"start": "New York, NY", "finish": "Chicago, IL"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(res.data["error"], "No feasible fuel-stop plan exists for this route.")
        self.assertEqual(res.data["route"]["distance_miles"], 800.0)

    @patch("routes.views.build_optimization_result")
    @patch("routes.views.optimize_route")
    @patch("routes.views.RoutingService")
    @patch("routes.views.GeocodingService")
    def test_feasible_route_returns_200_with_explicit_fuel_accounting(
        self,
        mock_geocoder_cls,
        mock_router_cls,
        mock_optimize_route,
        mock_build_result,
    ):
        mock_geocoder = mock_geocoder_cls.return_value
        mock_geocoder.geocode.side_effect = [
            {"longitude": -87.66, "latitude": 41.88, "label": "Chicago, IL"},
            {"longitude": -92.35, "latitude": 34.71, "label": "Little Rock, AR"},
        ]

        mock_router = mock_router_cls.return_value
        mock_router.get_route.return_value = {
            "distance_meters": 659.07 * 1609.344,
            "duration_seconds": 38965,
            "geometry": {"type": "LineString", "coordinates": [[-87.66, 41.88], [-92.35, 34.71]]},
        }

        mock_optimize_route.return_value = {"cost": 60.63, "path": ["START", "STATION_1", "FINISH"]}
        mock_build_result.return_value = {
            "path": ["START", "STATION_1", "FINISH"],
            "stops": [
                {
                    "id": 10,
                    "name": "Midway Station",
                    "city": "SampleCity",
                    "state": "IL",
                    "latitude": 39.5,
                    "longitude": -89.2,
                    "price_per_gallon": 3.30,
                    "route_mile": 475.0,
                    "gallons": 18.34,
                    "cost": 60.63,
                }
            ],
            "legs": [
                {"from": "START", "to": "STATION_1", "distance_miles": 475.0, "gallons": 0.0, "fuel_cost": 0.0},
                {"from": "STATION_1", "to": "FINISH", "distance_miles": 184.07, "gallons": 18.34, "fuel_cost": 60.63},
            ],
            "total_gallons_purchased": 18.34,
            "total_cost": 60.63,
        }

        res = self.client.post(
            "/api/v1/routes/optimize/",
            {"start": "Chicago, IL", "finish": "Little Rock, AR"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        fuel = res.data["fuel"]
        self.assertEqual(fuel["mpg"], 10)
        self.assertEqual(fuel["max_range_miles"], 500)
        self.assertEqual(fuel["starting_fuel_gallons"], 50)
        self.assertEqual(fuel["consumed_gallons"], 65.91)
        self.assertEqual(fuel["modeled_purchased_gallons"], 18.34)
        self.assertEqual(fuel["total_cost"], 60.63)
        self.assertEqual(len(res.data["fuel_stops"]), 1)
        self.assertEqual(res.data["fuel_stops"][0]["latitude"], 39.5)
        self.assertEqual(res.data["fuel_stops"][0]["longitude"], -89.2)
        self.assertEqual(len(res.data["legs"]), 2)

    def test_cors_headers_allowed(self):
        res = self.client.options(
            "/api/v1/routes/optimize/",
            HTTP_ORIGIN="http://127.0.0.1:5500",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), "*")

    @patch("routes.views.build_optimization_result")
    @patch("routes.views.optimize_route")
    @patch("routes.views.RoutingService")
    @patch("routes.views.GeocodingService")
    def test_repeated_request_uses_cache_and_skips_external_calls(
        self,
        mock_geocoder_cls,
        mock_router_cls,
        mock_optimize_route,
        mock_build_result,
    ):
        mock_geocoder = mock_geocoder_cls.return_value
        mock_geocoder.geocode.side_effect = [
            {"longitude": -87.66, "latitude": 41.88, "label": "Chicago, IL"},
            {"longitude": -92.35, "latitude": 34.71, "label": "Little Rock, AR"},
        ]

        mock_router = mock_router_cls.return_value
        mock_router.get_route.return_value = {
            "distance_meters": 659.07 * 1609.344,
            "duration_seconds": 38965,
            "geometry": {"type": "LineString", "coordinates": [[-87.66, 41.88], [-92.35, 34.71]]},
        }

        mock_optimize_route.return_value = {"cost": 60.63, "path": ["START", "STATION_1", "FINISH"]}
        mock_build_result.return_value = {
            "path": ["START", "STATION_1", "FINISH"],
            "stops": [],
            "legs": [],
            "total_gallons_purchased": 0.0,
            "total_cost": 60.63,
        }

        payload = {"start": "Chicago, IL", "finish": "Little Rock, AR"}

        # 1. First request -> MISS (calls geocoding & routing)
        res1 = self.client.post("/api/v1/routes/optimize/", payload, format="json")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res1.headers.get("X-Cache"), "MISS")
        self.assertEqual(mock_router.get_route.call_count, 1)

        # 2. Second request with different casing/spacing -> HIT (uses cache, zero new external calls)
        res2 = self.client.post(
            "/api/v1/routes/optimize/",
            {"start": "  chicago, il  ", "finish": "Little Rock, AR"},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.headers.get("X-Cache"), "HIT")
        # Ensure external services were NOT called a second time
        self.assertEqual(mock_router.get_route.call_count, 1)
        self.assertEqual(res1.data, res2.data)


class NewServicesAndTravelCopilotTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_geocoding_service_built_in_resolution(self):
        from routes.services.geocoding import GeocodingService
        geocoder = GeocodingService()
        result = geocoder.geocode("Chicago, IL")
        self.assertIn("longitude", result)
        self.assertIn("latitude", result)
        self.assertAlmostEqual(result["latitude"], 41.8781, delta=0.5)

    def test_routing_service_fallback(self):
        from routes.services.routing import RoutingService
        router = RoutingService()
        # Test fallback generator logic directly
        route = router._get_fallback_route(-87.62, 41.88, -92.28, 34.74)
        self.assertGreater(route["distance_meters"], 400000)
        self.assertEqual(route["geometry"]["type"], "LineString")
        self.assertGreater(len(route["geometry"]["coordinates"]), 10)

    def test_fuel_station_service_corridor_generation(self):
        """
        Verifies that FuelStationService generates realistic truck stops along route
        without needing any SQL database import.
        """
        from routes.services.station_service import FuelStationService
        service = FuelStationService()
        route_points = [
            {"longitude": -87.66, "latitude": 41.88, "mile": 0.0},
            {"longitude": -89.00, "latitude": 39.50, "mile": 200.0},
            {"longitude": -90.20, "latitude": 38.62, "mile": 350.0},
            {"longitude": -92.35, "latitude": 34.71, "mile": 650.0},
        ]
        candidates = service.get_candidate_stations_for_route(route_points, 650.0)
        self.assertGreater(len(candidates), 3)
        for cand in candidates:
            st = cand["station"]
            self.assertTrue(hasattr(st, "name"))
            self.assertTrue(hasattr(st, "retail_price"))
            self.assertTrue(2.50 <= float(st.retail_price) <= 4.50)
            self.assertGreaterEqual(cand["route_mile"], 0.0)
            self.assertLessEqual(cand["route_mile"], 650.0)

    def test_deterministic_travel_event_matching(self):
        """
        Validates deterministic route-aware matching:
        - Event near route is matched (affects_route = True)
        - Event far from route (e.g. Snoqualmie Pass, WA) is NOT matched (affects_route = False)
        - Performed without any LLM invocation
        """
        from routes.services.travel_events import TravelEventService
        service = TravelEventService()
        # Route passing through St. Louis (-90.199, 38.627) to Little Rock (-92.28, 34.74)
        route_points = [
            {"longitude": -87.66, "latitude": 41.88, "mile": 0.0},
            {"longitude": -89.50, "latitude": 40.00, "mile": 150.0},
            {"longitude": -90.20, "latitude": 38.63, "mile": 300.0},  # Intersects I-55 St. Louis event
            {"longitude": -92.28, "latitude": 34.74, "mile": 650.0},
        ]
        result = service.match_events_to_route(route_points, 650.0, default_tolerance_miles=15.0)
        self.assertTrue(result["has_matching_events"])
        matched_ids = [e["id"] for e in result["matched_events"]]
        self.assertIn("SIM-CLOSURE-5501", matched_ids)
        # Snoqualmie pass (Montana/Washington) must NOT be matched
        self.assertNotIn("SIM-OFFROUTE-9005", matched_ids)

        # Check Snoqualmie in all_events has affects_route = False
        off_route_event = next(e for e in result["all_events"] if e["id"] == "SIM-OFFROUTE-9005")
        self.assertFalse(off_route_event["affects_route"])

    def test_conditional_ai_zero_llm_calls_when_no_matching_event(self):
        """
        Crucial cost-conscious rule:
        No matching events and no explicit query = ZERO LLM calls!
        """
        from routes.services.bedrock_service import BedrockAdvisorService
        advisor = BedrockAdvisorService()
        res = advisor.generate_advisory(
            route_summary={"distance_miles": 100},
            matched_events=[],
            fuel_stops=[],
            user_query=None,
        )
        self.assertFalse(res["llm_used"])
        self.assertEqual(res["model"], "deterministic-rules")

    def test_voice_query_api_grounded_response(self):
        """
        Tests /api/v1/voice/query/ endpoint handles traveler questions
        grounded in backend data.
        """
        with patch("routes.services.bolna_service.GeocodingService") as mock_geo_cls, \
             patch("routes.services.bolna_service.RoutingService") as mock_route_cls:
            mock_geo = mock_geo_cls.return_value
            mock_geo.geocode.side_effect = [
                {"longitude": -87.66, "latitude": 41.88, "label": "Chicago, IL"},
                {"longitude": -92.28, "latitude": 34.74, "label": "Little Rock, AR"},
            ]
            mock_route = mock_route_cls.return_value
            mock_route.get_route.return_value = {
                "distance_meters": 650 * 1609.344,
                "duration_seconds": 36000,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-87.66, 41.88], [-90.20, 38.63], [-92.28, 34.74]],
                },
            }

            res = self.client.post(
                "/api/v1/voice/query/",
                {
                    "query": "What does this event mean for my route?",
                    "start": "Chicago, IL",
                    "finish": "Little Rock, AR",
                },
                format="json",
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertIn("spoken_answer", res.data)
            self.assertIn("affects_route", res.data)
            self.assertIn("route_summary", res.data)

    def test_travel_events_list_api(self):
        """
        Tests GET /api/v1/events/ returns registered events with explicit simulated labels.
        """
        res = self.client.get("/api/v1/events/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreater(res.data["count"], 0)
        events = res.data["events"]
        # Ensure simulated events are clearly flagged
        for evt in events:
            if evt["is_simulated"]:
                self.assertEqual(evt["source"], "SIMULATED")

    def test_copilot_hotel_booking_api(self):
        """Tests booking a corridor hotel."""
        res = self.client.post(
            "/api/v1/copilot/hotels/book/",
            {"hotel_id": "HTL-5501", "guest_name": "Trucker Joe", "rooms": 1},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "CONFIRMED")
        self.assertIn("confirmation_code", res.data)
        self.assertTrue(res.data["truck_parking"])

    def test_copilot_mechanic_dispatch_api(self):
        """Tests requesting roadside mechanic dispatch."""
        res = self.client.post(
            "/api/v1/copilot/mechanics/request/",
            {"mechanic_id": "MCH-5501", "issue": "Punctured Drive Tyre"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "DISPATCHED")
        self.assertIn("dispatch_id", res.data)
        self.assertIn("estimated_arrival_minutes", res.data)

    def test_copilot_parcel_drop_api(self):
        """Tests confirming a cargo delivery drop."""
        res = self.client.post(
            "/api/v1/copilot/parcels/drop/",
            {"tracking_id": "TRK-IND-8821", "notes": "Unloaded at Bay 4B"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "DELIVERED")
        self.assertIn("proof_of_delivery", res.data)

    def test_copilot_hospital_alert_api(self):
        """Tests sending emergency notification to hospital ER."""
        res = self.client.post(
            "/api/v1/copilot/hospitals/alert/",
            {"hospital_id": "HSP-5501", "condition": "Driver chest discomfort"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "ER_ALERTED_INCOMING")
        self.assertIn("alert_id", res.data)
        self.assertIn("emergency_phone", res.data)

    def test_copilot_sos_api(self):
        """Tests triggering emergency SOS broadcast."""
        res = self.client.post(
            "/api/v1/copilot/sos/",
            {"latitude": 38.627, "longitude": -90.199},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "ACTIVE_SOS_BROADCAST")
        self.assertIn("incident_id", res.data)
        self.assertGreater(len(res.data["dispatched_services"]), 0)

    def test_voice_query_multi_intent_routing(self):
        """Tests that spoken queries about hotels, mechanics, SOS route appropriately."""
        with patch("routes.services.bolna_service.GeocodingService") as mock_geo_cls, \
             patch("routes.services.bolna_service.RoutingService") as mock_route_cls:
            mock_geo = mock_geo_cls.return_value
            mock_geo.geocode.side_effect = [
                {"longitude": -87.66, "latitude": 41.88, "label": "Chicago, IL"},
                {"longitude": -92.28, "latitude": 34.74, "label": "Little Rock, AR"},
                {"longitude": -87.66, "latitude": 41.88, "label": "Chicago, IL"},
                {"longitude": -92.28, "latitude": 34.74, "label": "Little Rock, AR"},
                {"longitude": -87.66, "latitude": 41.88, "label": "Chicago, IL"},
                {"longitude": -92.28, "latitude": 34.74, "label": "Little Rock, AR"},
            ]
            mock_route = mock_route_cls.return_value
            mock_route.get_route.return_value = {
                "distance_meters": 650 * 1609.344,
                "duration_seconds": 36000,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-87.66, 41.88], [-90.20, 38.63], [-92.28, 34.74]],
                },
            }

            # 1. Hotel query
            res_hotel = self.client.post(
                "/api/v1/voice/query/",
                {"query": "Find me a motel with truck parking", "start": "Chicago, IL", "finish": "Little Rock, AR"},
                format="json",
            )
            self.assertEqual(res_hotel.status_code, status.HTTP_200_OK)
            self.assertEqual(res_hotel.data["intent"], "hotel_search")

            # 2. Mechanic query
            res_mech = self.client.post(
                "/api/v1/voice/query/",
                {"query": "Urgent! Call a mechanic for a tyre puncture", "start": "Chicago, IL", "finish": "Little Rock, AR"},
                format="json",
            )
            self.assertEqual(res_mech.status_code, status.HTTP_200_OK)
            self.assertEqual(res_mech.data["intent"], "mechanic_dispatch")

            # 3. Emergency query
            res_sos = self.client.post(
                "/api/v1/voice/query/",
                {"query": "Emergency! Highway patrol help needed", "start": "Chicago, IL", "finish": "Little Rock, AR"},
                format="json",
            )
            self.assertEqual(res_sos.status_code, status.HTTP_200_OK)
            self.assertEqual(res_sos.data["intent"], "emergency_sos")

    def test_live_fuel_rates_api(self):
        """Tests zero-key live fuel rate endpoint returns daily OMC benchmark rates."""
        res = self.client.get("/api/v1/fuel/rates/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "success")
        self.assertIn("state_rates", res.data)
        rates = res.data["state_rates"]
        self.assertIn("DL", rates)
        self.assertIn("HR", rates)
        self.assertIn("MH", rates)
        self.assertIn("GJ", rates)
        self.assertIn("RJ", rates)
        self.assertGreater(rates["DL"]["diesel_inr"], 80)
        self.assertGreater(rates["MH"]["diesel_inr"], rates["DL"]["diesel_inr"])

    def test_fuel_price_service_arbitrage(self):
        """Tests deterministic state geo-mapping, station price enrichment, and tax arbitrage calculation."""
        from routes.services.fuel_price_service import FuelPriceService
        service = FuelPriceService()

        # Deterministic state resolution along NH 48
        self.assertEqual(service.resolve_state_from_coords(28.5, 77.1), "DL")
        self.assertEqual(service.resolve_state_from_coords(28.2, 76.8), "HR")
        self.assertEqual(service.resolve_state_from_coords(26.9, 75.8), "RJ")
        self.assertEqual(service.resolve_state_from_coords(23.0, 72.5), "GJ")
        self.assertEqual(service.resolve_state_from_coords(19.1, 72.9), "MH")

        # Enrichment
        station_hr = {"id": 1, "latitude": 28.2, "longitude": 76.8, "name": "Bawal Highway Bunk"}
        enriched_hr = service.enrich_station_with_live_price(station_hr)
        self.assertEqual(enriched_hr["state_code"], "HR")
        self.assertIn("price_per_liter", enriched_hr)
        self.assertGreater(enriched_hr["savings_per_liter"], 0)

        station_mh = {"id": 2, "latitude": 19.1, "longitude": 72.9, "name": "Thane Diesel Hub"}
        enriched_mh = service.enrich_station_with_live_price(station_mh)
        self.assertEqual(enriched_mh["state_code"], "MH")

        # Strategy calculation
        strategy = service.generate_fuel_savings_strategy([enriched_hr, enriched_mh], language="hi")
        self.assertTrue(strategy["has_strategy"])
        self.assertGreater(strategy["diff_per_liter_inr"], 1.5)
        self.assertGreater(strategy["estimated_tank_savings_inr"], 1000)
        self.assertIn("बचत", strategy["advisory"])

    def test_voice_query_caching(self):
        """Tests that repeated voice queries return cached response with X-Cache HIT."""
        with patch("routes.services.bolna_service.GeocodingService") as mock_geo_cls, \
             patch("routes.services.bolna_service.RoutingService") as mock_route_cls:
            mock_geo = mock_geo_cls.return_value
            mock_geo.geocode.side_effect = [
                {"longitude": 77.2, "latitude": 28.6, "label": "Delhi"},
                {"longitude": 72.8, "latitude": 19.0, "label": "Mumbai"},
            ]
            mock_route = mock_route_cls.return_value
            mock_route.get_route.return_value = {
                "distance_meters": 1400 * 1000,
                "duration_seconds": 72000,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[77.2, 28.6], [75.8, 26.9], [72.8, 19.0]],
                },
            }

            # First request - MISS
            res1 = self.client.post(
                "/api/v1/voice/query/",
                {"query": "Nearest diesel pump station", "start": "Delhi", "finish": "Mumbai", "language": "en"},
                format="json",
            )
            self.assertEqual(res1.status_code, status.HTTP_200_OK)
            self.assertEqual(res1.headers.get("X-Cache"), "MISS")

            # Second identical request - HIT (instant response from cache)
            res2 = self.client.post(
                "/api/v1/voice/query/",
                {"query": "Nearest diesel pump station", "start": "Delhi", "finish": "Mumbai", "language": "en"},
                format="json",
            )
            self.assertEqual(res2.status_code, status.HTTP_200_OK)
            self.assertEqual(res2.headers.get("X-Cache"), "HIT")
            self.assertEqual(res2.data["spoken_answer"], res1.data["spoken_answer"])







class WeatherHazardServiceTests(TestCase):
    def test_fetch_batch_weather_empty_coords(self):
        from routes.services.weather_service import fetch_batch_weather
        res = fetch_batch_weather([])
        self.assertEqual(res, [])

    @patch("routes.services.weather_service.requests.get")
    def test_fetch_batch_weather_success(self, mock_get):
        from routes.services.weather_service import fetch_batch_weather
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "latitude": 28.5,
                "longitude": 77.1,
                "hourly": {
                    "time": ["2026-10-27T10:00"],
                    "wind_speed_10m": [15.5],
                    "rain": [0.1],
                    "snowfall": [0.0],
                    "temperature_2m": [65.0],
                },
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        coords = [(77.1, 28.5)]
        res = fetch_batch_weather(coords)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["hourly"]["wind_speed_10m"], [15.5])
        mock_get.assert_called_once()

    @patch("routes.services.weather_service.requests.get")
    def test_fetch_batch_weather_fallback_on_exception(self, mock_get):
        from routes.services.weather_service import fetch_batch_weather
        import requests
        mock_get.side_effect = requests.RequestException("Network timeout")

        coords = [(77.1, 28.5), (75.8, 26.9)]
        res = fetch_batch_weather(coords)
        self.assertEqual(len(res), 2)
        # Should return baseline fallback
        self.assertEqual(len(res[0]["hourly"]["time"]), 48)
        self.assertEqual(res[0]["hourly"]["wind_speed_10m"][0], 12.0)

    def test_get_checkpoint_weather_at_eta(self):
        from routes.services.weather_service import get_checkpoint_weather_at_eta
        import datetime
        fc = {
            "hourly": {
                "time": ["2026-10-27T10:00", "2026-10-27T11:00"],
                "wind_speed_10m": [22.4, 38.6],
                "rain": [0.05, 0.45],
                "snowfall": [0.0, 0.25],
                "temperature_2m": [55.0, 31.0],
            }
        }
        eta = datetime.datetime.fromisoformat("2026-10-27T11:15")
        weather = get_checkpoint_weather_at_eta(fc, eta)
        self.assertEqual(weather["wind_speed_mph"], 38.6)
        self.assertEqual(weather["rain_rate_in_hr"], 0.45)
        self.assertEqual(weather["snow_rate_in_hr"], 0.25)
        self.assertEqual(weather["temperature_f"], 31.0)

    @patch("routes.services.weather_service.fetch_batch_weather")
    def test_analyze_route_weather_hazards_detection(self, mock_fetch):
        from routes.services.weather_service import analyze_route_weather_hazards
        mock_fetch.return_value = [
            {
                "hourly": {
                    "time": ["2026-10-27T10:00", "2026-10-27T11:00", "2026-10-27T12:00"],
                    "wind_speed_10m": [36.0, 36.0, 36.0],
                    "rain": [0.0, 0.0, 0.0],
                    "snowfall": [0.2, 0.2, 0.2],
                    "temperature_2m": [28.0, 28.0, 28.0],
                }
            },
            {
                "hourly": {
                    "time": ["2026-10-27T10:00", "2026-10-27T11:00", "2026-10-27T12:00"],
                    "wind_speed_10m": [10.0, 10.0, 10.0],
                    "rain": [0.55, 0.55, 0.55],
                    "snowfall": [0.0, 0.0, 0.0],
                    "temperature_2m": [60.0, 60.0, 60.0],
                }
            },
        ]
        points = [
            {"mile": 0.0, "latitude": 28.6, "longitude": 77.2},
            {"mile": 60.0, "latitude": 27.8, "longitude": 76.5},
        ]
        result = analyze_route_weather_hazards(points)
        self.assertIn("weather_hazards", result)
        self.assertIn("checkpoints", result)
        hazards = result["weather_hazards"]
        hazard_types = [h["id"].split("-")[1] for h in hazards]
        self.assertIn("WIND", hazard_types)
        self.assertIn("SNOW", hazard_types)
        self.assertIn("RAIN", hazard_types)



class TripManifestServiceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.sample_route_data = {
            "route": {
                "distance_miles": 878.5,
                "duration_minutes": 1350.0,
                "start": {"label": "Delhi NCT, India"},
                "finish": {"label": "Mumbai, Maharashtra, India"},
            },
            "fuel": {
                "consumed_gallons": 87.85,
                "total_cost": 312.45,
            },
            "fuel_stops": [
                {
                    "name": "Bawal IndianOil Hub",
                    "city": "Rewari",
                    "state": "HR",
                    "route_mile": 55.4,
                    "retail_price": 89.65,
                    "price_per_liter": 89.65,
                    "gallons_to_buy": 40.0,
                }
            ],
            "live_fuel_strategy": {
                "has_strategy": True,
                "advisory": "Tank up in Haryana (HR) to save approx ₹1,200 vs Maharashtra (MH).",
            },
            "travel_events": {
                "active_route_alerts": [
                    {
                        "type": "WEATHER_HAZARD",
                        "title": "High Wind Caution",
                        "severity": "WARNING",
                        "route_mile": 120.0,
                        "recommended_action": "Reduce truck speed.",
                    }
                ]
            },
            "copilot_amenities": {
                "hospitals": [
                    {
                        "name": "Rewari Trauma Hospital",
                        "phone": "01274-255100",
                        "city": "Rewari",
                    }
                ],
                "mechanics": [
                    {
                        "name": "Highway Tyre Express",
                        "phone": "9812345678",
                        "city": "Bawal",
                    }
                ],
            },
        }

    def test_generate_manifest_structure(self):
        from routes.services.manifest_service import TripManifestService
        service = TripManifestService()
        manifest = service.generate_manifest(self.sample_route_data)

        self.assertEqual(manifest["status"], "success")
        self.assertTrue(manifest["manifest_id"].startswith("BLT-"))
        self.assertEqual(manifest["corridor"]["start"], "Delhi NCT, India")
        self.assertEqual(manifest["corridor"]["finish"], "Mumbai, Maharashtra, India")
        self.assertAlmostEqual(manifest["corridor"]["distance_km"], 1413.8, delta=1.0)
        self.assertIn("fuel_manifest", manifest)
        self.assertIn("emergency_dispatch", manifest)
        self.assertIn("printable_waybill", manifest)
        self.assertIn("Rewari Trauma Hospital", manifest["printable_waybill"])

    def test_manifest_export_api_with_payload(self):
        res = self.client.post(
            "/api/v1/routes/manifest/",
            {"route_data": self.sample_route_data},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "success")
        self.assertIn("printable_waybill", res.data)
        self.assertIn("manifest_id", res.data)
