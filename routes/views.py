from rest_framework.response import Response
from rest_framework.views import APIView

from routes.services.routing import RoutingService
from routes.services.geocoding import GeocodingService
from routes.services.route_geometry import build_route_points
from routes.services.station_projection import find_candidate_stations
from routes.services.route_graph import (
    build_route_nodes,
    build_route_graph,
)
from routes.services.optimizer import (
    optimize_route,
    build_optimization_result,
)
from .models import FuelStation


class HealthView(APIView):
    def get(self, request):
        return Response({
            "status": "ok"
        })


class DbCheckView(APIView):
    def get(self, request):
        records = FuelStation.objects.all()

        return Response({
            "connected": True,
            "records": [
                {
                    "id": record.id,
                    "name": record.name
                }
                for record in records
            ]
        })


class RouteTestView(APIView):
    def get(self, request):

        geocoder = GeocodingService()
        router = RoutingService()

        start = geocoder.geocode("New York, NY")
        finish = geocoder.geocode("Chicago, IL")

        route = router.get_route(
            (start["longitude"], start["latitude"]),
            (finish["longitude"], finish["latitude"]),
        )

        distance_miles = route["distance_meters"] / 1609.344

        route_points = build_route_points(
            route["geometry"],
            distance_miles,
        )

        stations = FuelStation.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False,
        )

        candidates = find_candidate_stations(
            stations,
            route_points,
        )
        nodes = build_route_nodes(
            candidates,
            distance_miles,
        )

        graph = build_route_graph(nodes)

        result = optimize_route(
            nodes,
            graph,
        )

        optimization = optimize_route(
            nodes,
            graph,
        )

        optimization_result = build_optimization_result(
            optimization,
            nodes,
            graph,
        )

        return Response({
            "start": start,
            "finish": finish,
            "distance_miles": distance_miles,
            "duration_minutes": route["duration_seconds"] / 60,
            "route_point_count": len(route_points),
            "candidate_station_count": len(candidates),
            "candidates": [
                {
                    "id": candidate["station"].id,
                    "name": candidate["station"].name,
                    "city": candidate["station"].city,
                    "state": candidate["station"].state,
                    "price": float(
                        candidate["station"].retail_price
                    ),
                    "route_mile": candidate["route_mile"],
                    "distance_to_route": candidate[
                        "distance_to_route"
                    ],
                }
                for candidate in candidates
            ],
            "graph": {
            "nodes": [
                {
                    "id": node["id"],
                    "type": node["type"],
                    "route_mile": node["route_mile"],
                }
                for node in nodes
            ],
            "edges": graph,
            "optimization": optimization_result,
        },
        })