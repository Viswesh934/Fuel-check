from unittest.mock import patch, MagicMock
from django.test import TestCase
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
        station_expensive = MagicMock(id=1, name="Expensive Gas", city="CityA", state="IL", retail_price=4.50)
        station_cheap = MagicMock(id=2, name="Cheap Gas", city="CityB", state="IL", retail_price=2.80)

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
        self.assertEqual(len(res.data["legs"]), 2)
